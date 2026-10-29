"""Validación común de reglas adultas indexadas contra el corpus autorizado.

Los TXT solo son referencia de integridad; nunca se devuelven como evidencia.
Una incidencia de un par autorizado queda bloqueada durante toda la consulta.
"""
import re
from pathlib import Path

BLOCK = re.compile(r'\[\[REGLA:([a-z_]+)\]\]\s*(.*?)\s*\[\[FIN\]\]', re.S)
START = re.compile(r'\[\[REGLA:([a-z_]+)\]\]')
CORPUS = Path(__file__).resolve().parents[2] / 'data' / 'raw'


class RuleIntegrity:
    def __init__(self, authorized):
        self.authorized = set(authorized)
        self.approved = {}
        self.found = {}
        self.seen = {}
        self.rejected = {}
        for file in sorted({key[0] for key in self.authorized}):
            try:
                text = (CORPUS / file).read_text(encoding='utf-8')
            except (OSError, UnicodeError):
                continue
            blocks = list(BLOCK.finditer(text))
            ids = [m[1] for m in blocks]
            if len(ids) != len(set(ids)) or len(START.findall(text)) != len(blocks) or text.count('[[FIN]]') != len(blocks):
                continue
            for chunk, match in enumerate(blocks):
                if match[2].strip() and len(match[0]) <= 1800:
                    self.approved[file, match[1]] = (match[0].strip(), chunk)

    def reject(self, key, reason):
        self.rejected.setdefault(key, set()).add(reason)
        self.found.pop(key, None)

    def add(self, candidates):
        for candidate in candidates:
            meta = candidate.get('metadata', {})
            if not isinstance(meta, dict):
                continue
            file, raw = meta.get('archivo'), candidate.get('contenido')
            if not isinstance(file, str) or file not in {k[0] for k in self.authorized}:
                continue  # Resultados de otros procedimientos no son evidencia autorizada.
            if not isinstance(raw, str):
                continue
            ids = START.findall(raw)
            keys = {(file, rule) for rule in ids if (file, rule) in self.authorized}
            if isinstance(meta.get('regla'), str) and (file, meta['regla']) in self.authorized:
                keys.add((file, meta['regla']))
            match = BLOCK.fullmatch(raw.strip())
            for key in keys:
                versions = self.seen.setdefault(key, set())
                versions.add(raw.strip())
                if len(versions) > 1:
                    self.reject(key, 'versiones_contradictorias')
                if not match or not match[2].strip() or len(raw) > 1800 or key[1] != match[1]:
                    self.reject(key, 'regla_incompleta_o_invalida')
                    continue
                approved = self.approved.get(key)
                if not approved or approved[0] != raw.strip():
                    self.reject(key, 'distinta_del_corpus_vigente')
                    continue
                chunk = meta.get('chunk')
                if (type(chunk) is not int or chunk != approved[1]
                        or meta.get('regla', match[1]) != match[1]
                        or ('id' in meta and meta['id'] != f'{file}::chunk_{chunk}')):
                    self.reject(key, 'metadata_invalida')
                    continue
                if key not in self.rejected:
                    self.found.setdefault(key, candidate)

    def diagnostics(self):
        return [f'{file}#{rule}:{reason}' for (file, rule), reasons in sorted(self.rejected.items())
                for reason in sorted(reasons)]


class IntegrityResults(list):
    """Lista compatible con consumidores previos, con diagnóstico sin texto libre."""
    def __init__(self, validator):
        super().__init__(validator.found[key] for key in sorted(validator.found))
        self.rejected = validator.rejected
