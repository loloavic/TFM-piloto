"""Diagnóstico local del índice, sin embeddings salvo --consulta explícita."""
import argparse
import json
from pathlib import Path

from app.graph.adult_context import ADULT_FILES
from app.rag.exact_rules import cargar_indice_exacto
from app.rag.rule_integrity import BLOCK as _BLOCK
from app.rag.index_builder import VECTOR_STORE_PATH
from app.rag.document_loader import cargar_documentos_txt
from app.rag.text_splitter import dividir_documentos


def diagnosticar_indice(ruta_indice=VECTOR_STORE_PATH, ruta_documentos='data/raw'):
    current=dividir_documentos(cargar_documentos_txt(ruta_documentos))
    expected={}
    for f in current:
        match=_BLOCK.fullmatch(f['contenido'].strip())
        if match:
            expected[f['archivo'],match[1]]=f['contenido'].strip()
    index=cargar_indice_exacto(ruta_indice)
    indexed,invalid={},[]
    adult_files=set(ADULT_FILES.values()) | {'dni_mayor_estado_civil.txt'}
    for identifier in dict.fromkeys(index.index_to_docstore_id.values()):
        doc=index.docstore.search(identifier)
        if not hasattr(doc,'metadata') or doc.metadata.get('archivo') not in adult_files:
            continue
        file=doc.metadata['archivo']
        match=_BLOCK.fullmatch(doc.page_content.strip())
        if not match or not match[2].strip():
            invalid.append({'archivo':file,'chunk':doc.metadata.get('chunk')})
            continue
        indexed.setdefault((file,match[1]),set()).add(doc.page_content.strip())
    statuses={}
    for key,text in sorted(expected.items()):
        versions=indexed.get(key,set())
        statuses['#'.join(key)]=('ausente_del_indice' if not versions else
            'versiones_conflictivas' if len(versions)>1 else
            'coincide_con_txt_actual' if text in versions else 'distinta_del_txt_actual')
    return {'fragmentos_indexados':len(index.index_to_docstore_id),
            'fragmentos_corpus_actual':len(current),'reglas':statuses,'fragmentos_invalidos':invalid}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--indice',default=VECTOR_STORE_PATH)
    parser.add_argument('--documentos',default='data/raw')
    parser.add_argument('--consulta',help='Opcional: ejecuta dos búsquedas semánticas reales y consume embeddings.')
    parser.add_argument('--archivo',default='dni_mayor_estado_civil.txt')
    parser.add_argument('--regla',default='seguimiento')
    args=parser.parse_args()
    result=diagnosticar_indice(args.indice,args.documentos)
    if args.consulta:
        # Solo diagnóstico local; no se expone como endpoint de lectura de sesiones.
        from app.rag.retriever import cargar_vector_store
        store=cargar_vector_store(args.indice)
        result['ranking']={}
        for label,query in [('inicial',args.consulta),('reintento',f'{args.consulta} Fuente {args.archivo} REGLA {args.regla}')]:
            result['ranking'][label]=[{'archivo':d.metadata.get('archivo'),'chunk':d.metadata.get('chunk'),
                'reglas':[m[1] for m in _BLOCK.finditer(d.page_content)],'distancia':float(score)}
                for d,score in store.similarity_search_with_score(query,k=10)]
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
