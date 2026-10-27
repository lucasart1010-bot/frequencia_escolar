"""Regras de análise da frequência (Data Mart).

Funções puras em pandas: recebem DataFrames e devolvem DataFrames.
Assim dá para testar sem abrir o Streamlit.
"""
import pandas as pd

STATUS_DB = ["presente", "falta", "justificada"]

# Referência pública: LDB (Lei 9.394/1996), art. 24, VI -> frequência mínima de 75%
FREQUENCIA_MINIMA_LDB = 75.0


def _maior_sequencia(serie_bool) -> int:
    """Maior sequência de True consecutivos (ex.: 3 faltas seguidas)."""
    atual = melhor = 0
    for v in serie_bool:
        atual = atual + 1 if v else 0
        melhor = max(melhor, atual)
    return melhor


def resumo_por_aluno(
    alunos: pd.DataFrame,
    freq: pd.DataFrame,
    contar_justificadas: bool = False,
    limite_pct: float = 30.0,
    limite_seq: int = 3,
) -> pd.DataFrame:
    """Uma linha por aluno com totais, percentuais e flag de risco de evasão.

    Risco de evasão = `limite_seq` ausências seguidas OU `limite_pct`% de ausências.
    Por padrão só "Falta" conta como ausência; justificadas entram se
    `contar_justificadas=True`.
    """
    colunas = [
        "aluno_id", "nome", "turma", "contato", "dias", "presencas", "faltas", "justificadas",
        "ausencias", "seq_max", "pct_faltas", "pct_presenca", "risco", "abaixo_ldb", "motivo",
    ]
    if "contato" not in alunos.columns:
        alunos = alunos.assign(contato="")
    if freq is None or freq.empty:
        return pd.DataFrame(columns=colunas)

    d = freq.copy()
    d["data"] = pd.to_datetime(d["data"])
    contam = ["falta", "justificada"] if contar_justificadas else ["falta"]
    d["ausente"] = d["status"].isin(contam)
    d = d.sort_values(["aluno_id", "data"])

    r = d.groupby("aluno_id").agg(
        dias=("status", "size"),
        presencas=("status", lambda s: int((s == "presente").sum())),
        faltas=("status", lambda s: int((s == "falta").sum())),
        justificadas=("status", lambda s: int((s == "justificada").sum())),
        ausencias=("ausente", "sum"),
        seq_max=("ausente", _maior_sequencia),
    ).reset_index()

    r["pct_faltas"] = (r["ausencias"] / r["dias"] * 100).round(1)
    r["pct_presenca"] = (r["presencas"] / r["dias"] * 100).round(1)
    r["abaixo_ldb"] = r["pct_presenca"] < FREQUENCIA_MINIMA_LDB

    por_seq = r["seq_max"] >= limite_seq
    por_pct = r["pct_faltas"] >= limite_pct
    r["risco"] = por_seq | por_pct

    def _motivo(linha):
        m = []
        if linha["seq_max"] >= limite_seq:
            m.append(f"{int(linha['seq_max'])} faltas seguidas")
        if linha["pct_faltas"] >= limite_pct:
            m.append(f"{linha['pct_faltas']:.0f}% de faltas")
        return " + ".join(m)

    r["motivo"] = r.apply(_motivo, axis=1)

    r = r.merge(alunos[["id", "nome", "turma", "contato"]], left_on="aluno_id", right_on="id", how="left").drop(columns="id")
    r["ausencias"] = r["ausencias"].astype(int)
    return r[colunas].sort_values(["risco", "ausencias", "nome"], ascending=[False, False, True]).reset_index(drop=True)


def distribuicao_status(freq: pd.DataFrame) -> pd.DataFrame:
    """Contagem de cada status (para o gráfico de pizza)."""
    nomes = {"presente": "Presente", "falta": "Falta", "justificada": "Falta Justificada"}
    cont = freq["status"].value_counts().reindex(STATUS_DB, fill_value=0)
    return pd.DataFrame({"status": [nomes[s] for s in cont.index], "total": cont.values})
