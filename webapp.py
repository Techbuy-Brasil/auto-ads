import os
import json
from datetime import datetime
from functools import wraps
from flask import (
    Flask, render_template, request, redirect,
    url_for, flash, session
)
from config_manager import adicionar, atualizar, remover, obter, todos
from ads_manager import AdManager, AdsError, Campaign

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
    return render_template("dashboard.html", clientes=todos())


# ── Clientes ────────────────────────────────────────────────

@app.route("/clientes/novo", methods=["GET", "POST"])
@login_required
def clientes_novo():
    if request.method == "POST":
        cid = request.form.get("id")
        nome = request.form.get("nome")
        ad_account = request.form.get("ad_account_id")
        token = request.form.get("access_token")
        page_id = request.form.get("page_id")
        if not all([cid, nome, ad_account, token]):
            flash("Preencha todos os campos", "error")
        else:
            adicionar(cid, nome, ad_account, token, page_id)
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
                  access_token=request.form.get("access_token"),
                  page_id=request.form.get("page_id"))
        flash("Cliente atualizado!", "success")
        return redirect(url_for("dashboard"))
    return render_template("cliente_form.html", cliente=cliente, client_id=client_id)


@app.route("/clientes/remover/<client_id>")
@login_required
def clientes_remover(client_id):
    remover(client_id)
    flash("Cliente removido!", "success")
    return redirect(url_for("dashboard"))


# ── Campanhas ──────────────────────────────────────────────

@app.route("/campanhas/<client_id>")
@login_required
def campanhas(client_id):
    cliente = obter(client_id)
    if not cliente:
        flash("Cliente não encontrado", "error")
        return redirect(url_for("dashboard"))
    try:
        mgr = AdManager(cliente["access_token"], cliente["ad_account_id"])
        return render_template("campanhas.html", campanhas=mgr.listar_campanhas(),
                               cliente=cliente, client_id=client_id)
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
        try:
            camp = mgr.criar_campanha(
                nome=request.form["nome"],
                objetivo=request.form["objetivo"],
                daily_budget=request.form["daily_budget"],
                status=request.form.get("status", "PAUSED"),
            )
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
        try:
            AdManager(cliente["access_token"], cliente["ad_account_id"]).pausar_campanha(campaign_id)
            flash("Campanha pausada!", "success")
        except AdsError as e:
            flash(f"Erro: {e}", "error")
    return redirect(url_for("campanhas", client_id=client_id))


@app.route("/campanhas/ativar/<client_id>/<campaign_id>")
@login_required
def campanhas_ativar(client_id, campaign_id):
    cliente = obter(client_id)
    if cliente:
        try:
            AdManager(cliente["access_token"], cliente["ad_account_id"]).ativar_campanha(campaign_id)
            flash("Campanha ativada!", "success")
        except AdsError as e:
            flash(f"Erro: {e}", "error")
    return redirect(url_for("campanhas", client_id=client_id))


# ── Wizard Completo (Campanha + Segmentação + Criativo) ────

@app.route("/wizard/<client_id>/passo1", methods=["GET", "POST"])
@login_required
def wizard_passo1(client_id):
    cliente = obter(client_id)
    if not cliente:
        flash("Cliente não encontrado", "error")
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        session["wizard"] = {
            "campanha": {
                "nome": request.form["nome"],
                "objetivo": request.form["objetivo"],
                "daily_budget": request.form["daily_budget"],
            }
        }
        return redirect(url_for("wizard_passo2", client_id=client_id))
    return render_template("wizard_passo1.html", cliente=cliente, client_id=client_id)


@app.route("/wizard/<client_id>/passo2", methods=["GET", "POST"])
@login_required
def wizard_passo2(client_id):
    if "wizard" not in session:
        return redirect(url_for("wizard_passo1", client_id=client_id))
    if request.method == "POST":
        session["wizard"]["segmentacao"] = {
            "locais": request.form.get("locais", ""),
            "idade_min": request.form.get("idade_min", ""),
            "idade_max": request.form.get("idade_max", ""),
            "genero": request.form.get("genero", ""),
            "interesses": request.form.get("interesses", ""),
        }
        return redirect(url_for("wizard_passo3", client_id=client_id))
    return render_template("wizard_passo2.html", client_id=client_id)


@app.route("/wizard/<client_id>/passo3", methods=["GET", "POST"])
@login_required
def wizard_passo3(client_id):
    if "wizard" not in session:
        return redirect(url_for("wizard_passo1", client_id=client_id))
    cliente = obter(client_id)
    if request.method == "POST":
        file = request.files.get("imagem")
        image_path = None
        if file and file.filename:
            filename = f"{datetime.now().timestamp()}_{file.filename}"
            image_path = os.path.join(UPLOAD_FOLDER, filename)
            file.save(image_path)

        session["wizard"]["criativo"] = {
            "page_id": request.form.get("page_id", ""),
            "link": request.form.get("link", ""),
            "headline": request.form.get("headline", ""),
            "descricao": request.form.get("descricao", ""),
            "cta": request.form.get("cta", "SAIBA_MAIS"),
            "image_path": image_path,
        }
        return redirect(url_for("wizard_revisar", client_id=client_id))
    return render_template("wizard_passo3.html", cliente=cliente, client_id=client_id)


@app.route("/wizard/<client_id>/revisar", methods=["GET", "POST"])
@login_required
def wizard_revisar(client_id):
    if "wizard" not in session:
        return redirect(url_for("wizard_passo1", client_id=client_id))
    cliente = obter(client_id)
    dados = session["wizard"]

    if request.method == "POST":
        mgr = AdManager(cliente["access_token"], cliente["ad_account_id"])
        try:
            resultado = mgr.criar_campanha_completa(dados)
            session.pop("wizard", None)
            flash(f"Campanha criada com sucesso! IDs: {resultado}", "success")
            return redirect(url_for("campanhas", client_id=client_id))
        except AdsError as e:
            flash(f"Erro: {e}", "error")
            return redirect(url_for("wizard_revisar", client_id=client_id))

    return render_template("wizard_revisar.html", dados=dados,
                           cliente=cliente, client_id=client_id)


# ── Conjuntos ──────────────────────────────────────────────

@app.route("/conjuntos/<client_id>/<campaign_id>")
@login_required
def conjuntos(client_id, campaign_id):
    cliente = obter(client_id)
    if not cliente:
        flash("Cliente não encontrado", "error")
        return redirect(url_for("dashboard"))
    try:
        mgr = AdManager(cliente["access_token"], cliente["ad_account_id"])
        lista = mgr.listar_conjuntos(campaign_id)
        return render_template("conjuntos.html", conjuntos=lista,
                               cliente=cliente, client_id=client_id,
                               campaign_id=campaign_id)
    except AdsError as e:
        flash(f"Erro: {e}", "error")
        return redirect(url_for("campanhas", client_id=client_id))


# ── Anúncios ──────────────────────────────────────────────

@app.route("/anuncios/<client_id>/<adset_id>")
@login_required
def anuncios(client_id, adset_id):
    cliente = obter(client_id)
    if not cliente:
        flash("Cliente não encontrado", "error")
        return redirect(url_for("dashboard"))
    try:
        mgr = AdManager(cliente["access_token"], cliente["ad_account_id"])
        lista = mgr.listar_anuncios(adset_id)
        return render_template("anuncios.html", anuncios=lista,
                               cliente=cliente, client_id=client_id,
                               adset_id=adset_id)
    except AdsError as e:
        flash(f"Erro: {e}", "error")
        return redirect(url_for("dashboard"))


# ── Config ────────────────────────────────────────────────

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
