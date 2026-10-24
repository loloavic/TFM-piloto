"""Serializa la transacción Gradio completa por conversación HTTP autorizada."""
import anyio
import gradio as gr


class ConversationBlocks(gr.Blocks):
    async def process_api(self, *args, **kwargs):
        # Gradio restaura SessionState antes de process_api, pero lee gr.State
        # y procesa las salidas dentro de él. Bloquear solo el callback deja
        # que dos eventos capturen el mismo estado inicial sin credencial.
        state = kwargs.get('state', args[2] if len(args) > 2 else None)
        if state is None:
            raise gr.Error('Sesión de interfaz no disponible; recargue la página.')
        mutex = getattr(state, '_tfm_conversation_mutex', None)
        if mutex is None:
            # Se ejecuta sin await en el único event loop ASGI soportado.
            # El cerrojo pertenece a SessionState y se libera con su expulsión;
            # no se almacena dentro del valor serializable de gr.State.
            mutex = anyio.Lock()
            state._tfm_conversation_mutex = mutex
        async with mutex:
            # Incluye lectura del estado, callback y actualización de salidas.
            return await super().process_api(*args, **kwargs)
