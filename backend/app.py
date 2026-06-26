"""
Backend Flask — Persistência em múltiplos formatos
Formatos: JSON, CSV, pickle, struct (campo fixo)
"""

import json
import csv
import pickle
import struct
import time
import os
import binascii
import requests
from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
os.makedirs(DATA_DIR, exist_ok=True)

JSON_PATH   = os.path.join(DATA_DIR, "dados.json")
CSV_PATH    = os.path.join(DATA_DIR, "dados.csv")
PKL_PATH    = os.path.join(DATA_DIR, "dados.pkl")
BIN_PATH    = os.path.join(DATA_DIR, "dados.bin")

API_URL = "https://jsonplaceholder.typicode.com/users"

# ── struct layout (registro de tamanho fixo) ────────────────────────────────
# id(I) + name(50s) + username(30s) + email(60s) + city(40s) + company(50s)
STRUCT_FMT  = "!I 50s 30s 60s 40s 50s"
STRUCT_SIZE = struct.calcsize(STRUCT_FMT)   # bytes por registro


def _encode(s: str, size: int) -> bytes:
    return s.encode("utf-8")[:size].ljust(size, b"\x00")


def _decode(b: bytes) -> str:
    return b.rstrip(b"\x00").decode("utf-8", errors="replace")


def user_to_struct(u: dict) -> bytes:
    return struct.pack(
        STRUCT_FMT,
        int(u.get("id", 0)),
        _encode(u.get("name", ""),                    50),
        _encode(u.get("username", ""),                30),
        _encode(u.get("email", ""),                   60),
        _encode(u.get("address", {}).get("city", ""), 40),
        _encode(u.get("company", {}).get("name", ""), 50),
    )


def struct_to_user(raw: bytes) -> dict:
    uid, name, username, email, city, company = struct.unpack(STRUCT_FMT, raw)
    return {
        "id":       uid,
        "name":     _decode(name),
        "username": _decode(username),
        "email":    _decode(email),
        "address":  {"city": _decode(city)},
        "company":  {"name": _decode(company)},
    }


# ── helpers de medição ───────────────────────────────────────────────────────

def _kb(path: str) -> float:
    try:
        return round(os.path.getsize(path) / 1024, 3)
    except FileNotFoundError:
        return 0.0


# ── salvar em todos os formatos ──────────────────────────────────────────────

def save_json(data):
    t0 = time.perf_counter()
    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return round((time.perf_counter() - t0) * 1000, 3)


def save_csv(data):
    if not data:
        return 0.0
    t0 = time.perf_counter()
    fields = ["id", "name", "username", "email", "city", "company"]
    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for u in data:
            writer.writerow({
                "id":       u.get("id", ""),
                "name":     u.get("name", ""),
                "username": u.get("username", ""),
                "email":    u.get("email", ""),
                "city":     u.get("address", {}).get("city", ""),
                "company":  u.get("company", {}).get("name", ""),
            })
    return round((time.perf_counter() - t0) * 1000, 3)


def save_pickle(data):
    t0 = time.perf_counter()
    with open(PKL_PATH, "wb") as f:
        pickle.dump(data, f)
    return round((time.perf_counter() - t0) * 1000, 3)


def save_struct(data):
    t0 = time.perf_counter()
    with open(BIN_PATH, "wb") as f:
        for u in data:
            f.write(user_to_struct(u))
    return round((time.perf_counter() - t0) * 1000, 3)


# ── carregar de cada formato ─────────────────────────────────────────────────

def load_json():
    t0 = time.perf_counter()
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data, round((time.perf_counter() - t0) * 1000, 3)


def load_csv():
    t0 = time.perf_counter()
    data = []
    with open(CSV_PATH, "r", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            data.append({
                "id":       int(row["id"]),
                "name":     row["name"],
                "username": row["username"],
                "email":    row["email"],
                "address":  {"city": row["city"]},
                "company":  {"name": row["company"]},
            })
    return data, round((time.perf_counter() - t0) * 1000, 3)


def load_pickle():
    t0 = time.perf_counter()
    with open(PKL_PATH, "rb") as f:
        data = pickle.load(f)
    return data, round((time.perf_counter() - t0) * 1000, 3)


def load_struct():
    t0 = time.perf_counter()
    data = []
    with open(BIN_PATH, "rb") as f:
        while True:
            raw = f.read(STRUCT_SIZE)
            if len(raw) < STRUCT_SIZE:
                break
            data.append(struct_to_user(raw))
    return data, round((time.perf_counter() - t0) * 1000, 3)


# ── endpoints ────────────────────────────────────────────────────────────────

@app.route("/carregar", methods=["GET"])
def carregar():
    """Baixa da API externa e já salva nos 4 formatos."""
    try:
        resp = requests.get(API_URL, timeout=8)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        return jsonify({"erro": f"Falha na API externa: {e}"}), 502

    tempos_salvar = {
        "json":   save_json(data),
        "csv":    save_csv(data),
        "pickle": save_pickle(data),
        "struct": save_struct(data),
    }

    return jsonify({
        "dados":         data,
        "tempos_salvar": tempos_salvar,
        "fonte":         "api",
    })


@app.route("/salvar", methods=["POST"])
def salvar():
    """Recebe JSON pelo body e grava nos 4 formatos."""
    data = request.get_json(force=True)
    if not isinstance(data, list):
        return jsonify({"erro": "Esperado array JSON"}), 400

    tempos = {
        "json":   save_json(data),
        "csv":    save_csv(data),
        "pickle": save_pickle(data),
        "struct": save_struct(data),
    }
    return jsonify({"ok": True, "tempos_salvar": tempos})


@app.route("/offline", methods=["GET"])
def offline():
    """Lê do arquivo salvo sem tocar na internet."""
    fmt = request.args.get("formato", "json")

    loaders = {
        "json":   load_json,
        "csv":    load_csv,
        "pickle": load_pickle,
        "struct": load_struct,
    }

    loader = loaders.get(fmt)
    if loader is None:
        return jsonify({"erro": "Formato inválido"}), 400

    path_map = {"json": JSON_PATH, "csv": CSV_PATH,
                "pickle": PKL_PATH, "struct": BIN_PATH}
    if not os.path.exists(path_map[fmt]):
        return jsonify({"erro": "Arquivo não encontrado. Carregue da API primeiro."}), 404

    try:
        data, tempo_carregar = loader()
    except Exception as e:
        return jsonify({"erro": str(e)}), 500

    return jsonify({
        "dados":          data,
        "tempo_carregar": tempo_carregar,
        "fonte":          f"arquivo:{fmt}",
    })


@app.route("/comparar", methods=["GET"])
def comparar():
    """Retorna tamanho (KB) e tempos de todos os formatos."""
    result = {}
    for fmt, path, loader in [
        ("json",   JSON_PATH, load_json),
        ("csv",    CSV_PATH,  load_csv),
        ("pickle", PKL_PATH,  load_pickle),
        ("struct", BIN_PATH,  load_struct),
    ]:
        existe = os.path.exists(path)
        if existe:
            try:
                _, t_load = loader()
            except Exception:
                t_load = None
        else:
            t_load = None

        result[fmt] = {
            "existe":         existe,
            "tamanho_kb":     _kb(path),
            "tempo_carregar": t_load,
        }

    return jsonify(result)


@app.route("/inspecionar", methods=["GET"])
def inspecionar():
    """Retorna amostra de texto (JSON) e hexdump do binário (pickle)."""
    resposta = {}

    # Amostra de texto — primeiros 600 chars do JSON
    if os.path.exists(JSON_PATH):
        with open(JSON_PATH, "r", encoding="utf-8") as f:
            resposta["json_amostra"] = f.read(600)
    else:
        resposta["json_amostra"] = None

    # Hexdump dos primeiros 256 bytes do pickle
    if os.path.exists(PKL_PATH):
        with open(PKL_PATH, "rb") as f:
            raw = f.read(256)
        hex_str = binascii.hexlify(raw).decode("ascii")
        # formata em linhas de 32 hex chars (16 bytes cada)
        linhas = [hex_str[i:i+32] for i in range(0, len(hex_str), 32)]
        resposta["pickle_hexdump"] = "\n".join(
            f"{i*16:04x}  " + " ".join(l[j:j+2] for j in range(0, len(l), 2))
            for i, l in enumerate(linhas)
        )
    else:
        resposta["pickle_hexdump"] = None

    return jsonify(resposta)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
