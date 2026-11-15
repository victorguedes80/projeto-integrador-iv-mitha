"""Caminhos compartilhados pelas análises locais."""

from pathlib import Path
import os
import ast
import json
import operator

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "src" / "tmp"  # Cache e materiais das explorações anteriores.
RESULTADOS = ROOT / "resultados_simulador"
CACHE = BASE / ".cache"
os.environ.setdefault("MPLCONFIGDIR", str(CACHE / "matplotlib"))


def saida_local(path):
    path = Path(path).resolve()
    if not path.is_relative_to(ROOT):
        raise ValueError("A saída deve ficar dentro da raiz do projeto")
    path.mkdir(parents=True, exist_ok=True)
    return path


def configuration():
    nb = json.loads((ROOT / "notebooks/analispi4.ipynb").read_text())
    names = {
        "ANO",
        "LINHA",
        "DISPOSITIVO_SOIL",
        "PASSO_MS",
        "DESVIO_PASSO_MS",
        "TOL_VALVE_MS",
        "TOL_SOIL_MS",
        "TOL_ENV_MS",
    }

    def literal(node):
        if isinstance(node, ast.BinOp):
            operation = {
                ast.Mult: operator.mul,
                ast.Add: operator.add,
                ast.Sub: operator.sub,
            }.get(type(node.op))
            if operation is not None:
                return operation(literal(node.left), literal(node.right))
        return ast.literal_eval(node)

    cfg = {}
    for cell in nb["cells"]:
        if cell["cell_type"] != "code":
            continue
        source = "".join(cell["source"])
        if "PASSO_MS =" not in source:
            continue
        for node in ast.parse(source).body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id in names:
                        cfg[target.id] = literal(node.value)
    if names - cfg.keys():
        raise ValueError(f"Configuração ausente: {names - cfg.keys()}")
    return cfg
