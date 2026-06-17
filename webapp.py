import os
import json
from datetime import datetime
from functools import wraps
from flask import (
    Flask, render_template, request, redirect,
    url_for, flash, session
)
from config_manager import adicionar, atualizar, remover, obter, todos
from facebook_business.adobjects.campaign import Campaign
from ads_manager import AdManager, AdsError

app = Flask(__name__)
app.secret_key = os.urandom(24).hex()
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config.json")


def _load_config():
    if not os.path.exists(CONFIG_FILE):
        return {"senha": "admin123"}
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_config(data):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        cfg = _load_config()
        if request.form.get("senha") == cfg["senha"]:
            session["logged_in"] = True
            return redirect(url_for("dashboard"))
        flash("Senha incorreta", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
@login_required
def dashboard():
    clientes = todos()
    return render_template("dashboard.html", clientes=clientes)


@app.route("/clientes/novo", methods=["GET", "POST"])
@login_required
def clientes_novo():
    if request.method == "POST":
        cid = request.form.get("id")
        nome = request.form.get("nome")
        ad_account = request.form.get("ad_account_id")
        token = request.form.get("access_token")
        if not all([cid, nome, ad_account, token]):
            flash("Preencha todos os campos", "error")
        else:
            adicionar(cid, nome, ad_account, token)
            flash(f"Cliente '{cid}' cadastrado!", "success")
            return redirect(url_for("dashboard"))
    return render_template("cliente_form.html", cliente=None)


@app.route("/clientes/editar/<client_id>", methods=["GET", "POST"])
@login_required
def clientes_editar(client_id):
    cliente = obter(client_id)
    if not cliente:
        flash("Cliente não encontrado", "error")
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        atualizar(client_id,
                  nome=request.form.get("nome"),
                  ad_account_id=request.form.get("ad_account_id"),
                  access_token=request.form.get("access_token"))
        flash("Cliente atualizado!", "success")
        return redirect(url_for("dashboard"))
    return render_template("cliente_form.html", cliente=cliente, client_id=client_id)


@app.route("/clientes/remover/<client_id>")
@login_required
def clientes_remover(client_id):
    remover(client_id)
    flash("Cliente removido!", "success")
    return redirect(url_for("dashboard"))


@app.route("/campanhas/<client_id>")
@login_required
def campanhas(client_id):
    cliente = obter(client_id)
    if not cliente:
        flash("Cliente não encontrado", "error")
        return redirect(url_for("dashboard"))
    try:
        mgr = AdManager(cliente["access_token"], cliente["ad_account_id"])
        lista = mgr.listar_campanhas()
        return render_template("campanhas.html", campanhas=lista, cliente=cliente,
                               client_id=client_id)
    except AdsError as e:
        flash(f"Erro: {e}", "error")
        return redirect(url_for("dashboard"))


@app.route("/campanhas/nova/<client_id>", methods=["GET", "POST"])
@login_required
def campanhas_nova(client_id):
    cliente = obter(client_id)
    if not cliente:
        flash("Cliente não encontrado", "error")
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        mgr = AdManager(cliente["access_token"], cliente["ad_account_id"])
        objetivo = request.form.get("objetivo")
        daily = request.form.get("daily_budget")
        nome = request.form.get("nome")
        status = request.form.get("status", "PAUSED")
        try:
            camp = mgr.criar_campanha(nome, objetivo, status, daily_budget=daily)
            flash(f"Campanha '{camp[Campaign.Field.name]}' criada!", "success")
            return redirect(url_for("campanhas", client_id=client_id))
        except AdsError as e:
            flash(f"Erro: {e}", "error")
    return render_template("campanha_form.html", cliente=cliente, client_id=client_id)


@app.route("/campanhas/pausar/<client_id>/<campaign_id>")
@login_required
def campanhas_pausar(client_id, campaign_id):
    cliente = obter(client_id)
    if cliente:
        mgr = AdManager(cliente["access_token"], cliente["ad_account_id"])
        try:
            mgr.pausar_campanha(campaign_id)
            flash("Campanha pausada!", "success")
        except AdsError as e:
            flash(f"Erro: {e}", "error")
    return redirect(url_for("campanhas", client_id=client_id))


@app.route("/campanhas/ativar/<client_id>/<campaign_id>")
@login_required
def campanhas_ativar(client_id, campaign_id):
    cliente = obter(client_id)
    if cliente:
        mgr = AdManager(cliente["access_token"], cliente["ad_account_id"])
        try:
            mgr.ativar_campanha(campaign_id)
            flash("Campanha ativada!", "success")
        except AdsError as e:
            flash(f"Erro: {e}", "error")
    return redirect(url_for("campanhas", client_id=client_id))


@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    if request.method == "POST":
        nova = request.form.get("nova_senha")
        if nova:
            cfg = _load_config()
            cfg["senha"] = nova
            _save_config(cfg)
            flash("Senha alterada!", "success")
    return render_template("settings.html")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    app.run(host="0.0.0.0", port=port, debug=True)
