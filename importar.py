"""Leitura da lista de alunos a partir de planilha (.xlsx ou .csv).

Procura a linha de cabeçalho que contém "nome" (ex.: "NOME DO ALUNO") e lê o nome e o
contato (coluna CONTATO / TELEFONE / CELULAR / WHATSAPP, guardado só com dígitos).
A data de nascimento e as demais colunas são ignoradas de propósito.
A turma vem do título acima do cabeçalho (ex.: "5º ANO B (TARDE) - 2026").
"""
import io

import pandas as pd

PARTICULAS = {"de", "da", "do", "dos", "das", "e"}


def nome_bonito(nome: str) -> str:
    palavras = nome.split()
    return " ".join(p.lower() if p.lower() in PARTICULAS else p.capitalize() for p in palavras)


def so_digitos(texto) -> str:
    return "".join(ch for ch in str(texto) if ch.isdigit())


def contato_valido(d: str) -> bool:
    """Telefone brasileiro com DDD: 10 (fixo) ou 11 dígitos (celular)."""
    return len(d) in (10, 11)


def formatar_contato(d: str) -> str:
    if not d:
        return ""
    if len(d) == 11:
        return f"({d[:2]}) {d[2:7]}-{d[7:]}"
    if len(d) == 10:
        return f"({d[:2]}) {d[2:6]}-{d[6:]}"
    return d  # tamanho fora do padrão: mostra como veio para a professora conferir


def link_whatsapp(d: str) -> str | None:
    return f"https://wa.me/55{d}" if contato_valido(d) else None


def _ler_csv(arquivo) -> pd.DataFrame:
    raw = arquivo.read() if hasattr(arquivo, "read") else open(arquivo, "rb").read()
    if isinstance(raw, bytes):
        try:
            raw = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            raw = raw.decode("latin-1")
    return pd.read_csv(io.StringIO(raw), header=None, dtype=str, sep=r"[;,\t]", engine="python")


def ler_planilha_alunos(arquivo) -> pd.DataFrame:
    """Devolve DataFrame com as colunas `nome`, `turma` e `contato` (sem duplicados)."""
    nome_arq = str(getattr(arquivo, "name", arquivo)).lower()
    if nome_arq.endswith(".csv"):
        bruto = _ler_csv(arquivo)
    else:
        bruto = pd.read_excel(arquivo, header=None, dtype=str)

    idx = col = None
    for i, linha in bruto.iterrows():
        for j, c in enumerate(linha):
            if isinstance(c, str) and "nome" in c.lower():
                idx, col = i, j
                break
        if idx is not None:
            break
    if idx is None:
        raise ValueError("não achei a coluna de nome (ex.: “NOME DO ALUNO”)")

    turma = "Turma A"
    for i in range(idx):  # título acima do cabeçalho
        textos = [c for c in bruto.iloc[i] if isinstance(c, str) and c.strip()]
        if textos:
            turma = textos[0].split(" - ")[0].strip().title()
            break

    cabecalho = [str(c).strip().lower() for c in bruto.iloc[idx]]
    col_cont = next((j for j, c in enumerate(cabecalho)
                     if any(k in c for k in ("contato", "telefone", "celular", "whatsapp"))), None)

    dados = bruto.iloc[idx + 1:]
    nomes = dados.iloc[:, col].fillna("").astype(str).str.strip()
    contatos = (dados.iloc[:, col_cont].fillna("").map(so_digitos) if col_cont is not None
                else pd.Series("", index=dados.index))
    ok = nomes != ""
    df = pd.DataFrame({"nome": nomes[ok].map(nome_bonito).values, "turma": turma,
                       "contato": contatos[ok].values})
    return df.drop_duplicates(subset="nome").reset_index(drop=True)
