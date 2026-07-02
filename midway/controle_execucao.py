import json
import logging
import os
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path


DATA_DIR = Path("data")
CONTROL_DIR = DATA_DIR / "control"
LOG_DIR = DATA_DIR / "logs"


def valor_verdadeiro(nome_variavel):
    return os.getenv(nome_variavel, "").strip().lower() in {
        "1",
        "true",
        "t",
        "yes",
        "y",
        "sim",
        "s",
    }


def agora_iso():
    return datetime.now().isoformat(timespec="seconds")


def preparar_diretorios_controle():
    CONTROL_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)


def caminho_done(etapa, anomes):
    return CONTROL_DIR / f"{etapa}_{anomes}.done.json"


def caminho_lock(etapa, anomes):
    return CONTROL_DIR / f"{etapa}_{anomes}.lock"


def caminho_log(etapa, anomes):
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    return LOG_DIR / f"{etapa}_{anomes}_{timestamp}.log"


def configurar_logger(etapa, anomes):
    preparar_diretorios_controle()
    logger = logging.getLogger(f"{etapa}_{anomes}")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    logger.propagate = False

    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    file_handler = logging.FileHandler(caminho_log(etapa, anomes), encoding="utf-8")
    file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)

    return logger


def carregar_done(etapa, anomes):
    done_path = caminho_done(etapa, anomes)

    if not done_path.exists():
        return None

    return json.loads(done_path.read_text(encoding="utf-8"))


def gravar_done(etapa, anomes, dados):
    preparar_diretorios_controle()
    done_path = caminho_done(etapa, anomes)
    payload = {
        "etapa": etapa,
        "anomes": anomes,
        "status": "success",
        **dados,
    }
    done_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def validar_done_sucesso(etapa, anomes):
    done = carregar_done(etapa, anomes)

    if not done:
        raise RuntimeError(
            f"Controle nao encontrado: {caminho_done(etapa, anomes)}"
        )

    if done.get("status") != "success":
        raise RuntimeError(
            f"Controle invalido para {etapa}/{anomes}: status={done.get('status')}"
        )

    return done


@contextmanager
def lock_execucao(etapa, anomes):
    preparar_diretorios_controle()
    lock_path = caminho_lock(etapa, anomes)
    started_at = agora_iso()

    try:
        fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise RuntimeError(
            f"Execucao ja em andamento ou lock pendente: {lock_path}. "
            "Se tiver certeza que nao existe processo rodando, remova o arquivo lock."
        ) from exc

    with os.fdopen(fd, "w", encoding="utf-8") as lock_file:
        json.dump(
            {
                "etapa": etapa,
                "anomes": anomes,
                "started_at": started_at,
                "pid": os.getpid(),
            },
            lock_file,
            ensure_ascii=False,
            indent=2,
        )

    try:
        yield started_at
    finally:
        if lock_path.exists():
            lock_path.unlink()
