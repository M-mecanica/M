import os
import json
import re
import unicodedata
import datetime
import random
from flask import (
    Flask, render_template, request, redirect,
    url_for, session, jsonify, make_response
)
from pymongo import MongoClient
from bson.objectid import ObjectId
from werkzeug.utils import secure_filename
import gridfs

app = Flask(__name__)
app.secret_key = "CHAVE_SECRETA_PARA_SESSAO"  # Troque por algo seguro em produção

# ------------------------ DB do M (m_plataforma) ----------------------------
client_m = MongoClient(
    "mongodb+srv://msolucoesmecanicasinteligentes:solucao@cluster0.7ljuh.mongodb.net/"
)
db_m = client_m["m_plataforma"]

# Coleções do M
problemas_collection = db_m["problemas"]
usuarios_collection = db_m["usuarios"]
history_collection = db_m["search_history"]          # Histórico de buscas de PEÇAS
problem_history_collection = db_m["problem_search_history"]  # Histórico de busca de PROBLEMAS
problem_view_history_collection = db_m["problem_view_history"]  # Registro de visualização de soluções
improvement_suggestions_collection = db_m["improvement_suggestions"]  # Sugestões de melhorias

# GridFS para armazenar as imagens no DB "m_plataforma"
fs_m = gridfs.GridFS(db_m)

# Coleção para armazenar os 200 problemas diários (p/ problemas)
daily_random_problems_collection = db_m["daily_random_problems"]

# ------------------------ DB do MZ (MachineZONE) ----------------------------
client_mz = MongoClient(
    "mongodb+srv://adaltonmuzilomendes:rolamento@cluster0.atmeh.mongodb.net/"
)
db_mz = client_mz["MachineZONE"]

# Coleção principal de itens no MZ
itens_collection = db_mz["itens"]
# Coleção para armazenar os 200 itens diários (p/ pesquisa de peças)
daily_random_items_collection = db_mz["daily_random_items"]

def user_is_logged_in():
    """Retorna True se há um usuário logado na sessão (banco 'm_plataforma')."""
    return "user_id" in session

def user_has_role(roles_permitidos):
    """
    Verifica se o usuário logado possui um dos papéis em 'roles_permitidos'.
    """
    if not user_is_logged_in():
        return False
    return session.get("role") in roles_permitidos

def save_image_if_exists(file_obj):
    """
    Salva o arquivo em GridFS e retorna o ID (string) do arquivo.
    Retorna None se não houver arquivo ou se estiver vazio.
    """
    if not file_obj or file_obj.filename.strip() == "":
        return None

    file_data = file_obj.read()
    if not file_data:
        return None

    content_type = file_obj.content_type
    filename = secure_filename(file_obj.filename)

    stored_id = fs_m.put(
        file_data,
        filename=filename,
        contentType=content_type
    )
    return str(stored_id)

def normalize_string(s):
    """
    Remove acentos e deixa tudo em minúsculo, sem espaços repetidos.
    Ex.: 'Rolamento grande' -> 'rolamento grande'
    """
    normalized = ''.join(
        c for c in unicodedata.normalize('NFKD', s)
        if not unicodedata.combining(c)
    )
    return re.sub(r'\s+', ' ', normalized.strip().lower())

def generate_sub_phrases(tokens):
    """
    Gera todas as sub-frases contíguas de uma lista de tokens.
    Ex.: ["rolamento","grande","da","redução"] -> várias sub-frases.
    """
    sub_phrases = []
    n = len(tokens)
    for start in range(n):
        for end in range(start + 1, n + 1):
            sub_slice = tokens[start:end]
            sub_phrases.append(" ".join(sub_slice))
    return sub_phrases

def compute_largest_sub_phrase_length(search_tokens, item_phrases):
    """
    Verifica a maior sub-frase (em nº de tokens) presente em 'item_phrases'.
    """
    if not item_phrases:
        return 0
    all_sub_phrases = generate_sub_phrases(search_tokens)
    largest_length = 0
    for subp in all_sub_phrases:
        if subp in item_phrases:
            num_tokens = len(subp.split())
            if num_tokens > largest_length:
                largest_length = num_tokens
    return largest_length

def get_today_date_str():
    """Retorna a data de hoje como string 'YYYY-MM-DD'."""
    return datetime.datetime.utcnow().strftime("%Y-%m-%d")

def get_daily_random_resolved_problems():
    """
    Retorna uma lista (em formato de ObjectId) com até 200 problemas
    (resolvidos) selecionados aleatoriamente para o dia atual.

    - Se já existir um documento para o dia de hoje, retorna a lista armazenada.
    - Caso contrário, seleciona aleatoriamente 200 problemas resolvidos,
      salva no documento do dia e retorna essa lista.
    """
    today_str = get_today_date_str()
    daily_doc = daily_random_problems_collection.find_one({"date_str": today_str})

    if daily_doc is not None:
        # Já temos o documento do dia, apenas retornamos a lista
        id_strings = daily_doc.get("problem_ids", [])
        return [ObjectId(pid) for pid in id_strings]
    else:
        # Gera 200 problemas resolvidos aleatórios
        pipeline = [
            {"$match": {"resolvido": True}},
            {"$sample": {"size": 200}}
        ]
        sampled = list(problemas_collection.aggregate(pipeline))
        selected_ids = [str(item["_id"]) for item in sampled]

        # Salva no documento para manter a mesma seleção o dia todo
        new_doc = {
            "date_str": today_str,
            "problem_ids": selected_ids
        }
        daily_random_problems_collection.insert_one(new_doc)

        return [ObjectId(pid) for pid in selected_ids]

def get_daily_random_items():
    """
    Retorna uma lista (em formato de ObjectId) com até 200 itens
    selecionados aleatoriamente (do acervo total) para o dia atual.

    - Se já existir um documento para o dia de hoje, retorna a lista armazenada.
    - Caso contrário, seleciona aleatoriamente 200 itens,
      salva no documento do dia e retorna essa lista.
    """
    today_str = get_today_date_str()
    daily_doc = daily_random_items_collection.find_one({"date_str": today_str})

    if daily_doc is not None:
        id_strings = daily_doc.get("item_ids", [])
        return [ObjectId(pid) for pid in id_strings]
    else:
        # Gera 200 itens aleatórios
        pipeline = [
            {"$sample": {"size": 200}}
        ]
        sampled = list(itens_collection.aggregate(pipeline))
        selected_ids = [str(item["_id"]) for item in sampled]

        new_doc = {
            "date_str": today_str,
            "item_ids": selected_ids
        }
        daily_random_items_collection.insert_one(new_doc)

        return [ObjectId(pid) for pid in selected_ids]


@app.route("/")
def root():
    """
    Ao abrir a aplicação pela primeira vez, redireciona para /index.
    """
    return redirect(url_for("index"))

@app.route("/index", methods=["GET"])
def index():
    """
    Página inicial da aplicação. Esta rota é acessível mesmo sem login.
    Se houver o parâmetro ?need_login=1, um modal deverá ser exibido
    informando ao usuário que ele precisa fazer login.
    """
    need_login = request.args.get("need_login", "0")
    return render_template("index.html", need_login=need_login)

@app.route("/login", methods=["GET", "POST"])
def login():
    """
    Formulário de login no sistema (banco 'm_plataforma', coleção 'usuarios').
    """
    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        senha = request.form.get("senha", "").strip()

        # Capitalizar cada palavra
        nome = " ".join(word.capitalize() for word in nome.split())

        usuario = usuarios_collection.find_one({"nome": nome, "senha": senha})
        if usuario:
            session["user_id"] = str(usuario["_id"])
            session["username"] = usuario["nome"]
            session["role"] = usuario["role"]
            return redirect(url_for("index"))
        else:
            erro = "Usuário ou senha inválidos."
            return render_template("login.html", erro=erro)
    return render_template("login.html", erro=None)

@app.route("/logout")
def logout():
    """ Encerra a sessão do usuário atual. """
    session.clear()
    return redirect(url_for("login"))

@app.route("/register", methods=["GET", "POST"])
def register():
    """
    Criação de um novo usuário. Roles possíveis (ex.: 'comum', 'solucionador', 'mecanico').
    Após o cadastro, o usuário é logado automaticamente e redirecionado à index.
    """
    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        senha = request.form.get("senha", "").strip()
        confirmar_senha = request.form.get("confirmar_senha", "").strip()
        role = "comum"
        whatsapp = request.form.get("whatsapp", "").strip()
        maquinas = request.form.get("maquinas", "").strip()

        if senha != confirmar_senha:
            erro = "As senhas não conferem!"
            return render_template("register.html", erro=erro)

        nome = " ".join(word.capitalize() for word in nome.split())

        # Verifica duplicado
        if usuarios_collection.find_one({"nome": nome}):
            erro = "Usuário já existe!"
            return render_template("register.html", erro=erro)

        novo_usuario = {
            "nome": nome,
            "senha": senha,
            "role": role,
            "whatsapp": whatsapp,
            "maquinas": maquinas
        }
        inserted = usuarios_collection.insert_one(novo_usuario)
        new_user_id = str(inserted.inserted_id)

        session["user_id"] = new_user_id
        session["username"] = nome
        session["role"] = role

        return redirect(url_for("index"))

    return render_template("register.html", erro=None)

##############################################################################
#                ROTAS DO M (m_plataforma) - PROBLEMAS
##############################################################################

@app.route("/search", methods=["GET"])
def search():
    """
    Pesquisa problemas resolvidos com base em 'q'.
    Se 'q' estiver vazio, mostra todos os problemas resolvidos,
    mas com 200 problemas aleatórios (selecionados 1x por dia) aparecendo primeiro
    e, a cada carregamento, a ordem desses 200 muda.
    Também registra histórico de pesquisa de PROBLEMAS (sem data/hora).
    """
    termo_busca = request.args.get("q", "").strip()

    if termo_busca:
        termo_busca_normalized = normalize_string(termo_busca)
        tokens = [t for t in termo_busca_normalized.split() if t]

        query = {
            "resolvido": True,
            "$or": [
                {"titulo": {"$regex": termo_busca, "$options": "i"}},
                {"tags": {"$all": tokens}}
            ]
        }

        # Log de pesquisa de problemas
        if user_is_logged_in():
            problem_history_collection.insert_one({
                "user_id": session["user_id"],
                "user_name": session["username"],
                "query": termo_busca
            })
        else:
            problem_history_collection.insert_one({
                "user_id": None,
                "user_name": "Guest",
                "query": termo_busca
            })

        problemas_encontrados = list(problemas_collection.find(query))
        for p in problemas_encontrados:
            p["_id_str"] = str(p["_id"])

        return render_template(
            "resultados.html",
            problemas=problemas_encontrados,
            termo_busca=termo_busca
        )
    else:
        # Sem termo de busca -> mostrar 200 diários + resto
        daily_ids = get_daily_random_resolved_problems()
        random.shuffle(daily_ids)

        # Carrega do banco
        daily_problems_cursor = problemas_collection.find({"_id": {"$in": daily_ids}})

        # Precisamos reordenar de acordo com a lista shuffled
        daily_map = {}
        for dp in daily_problems_cursor:
            daily_map[str(dp["_id"])] = dp

        daily_problems_list = []
        for did in daily_ids:
            did_str = str(did)
            if did_str in daily_map:
                item = daily_map[did_str]
                item["_id_str"] = did_str
                daily_problems_list.append(item)

        # Carrega os demais problemas resolvidos
        remaining_cursor = problemas_collection.find({
            "resolvido": True,
            "_id": {"$nin": daily_ids}
        })
        remaining_problems = list(remaining_cursor)
        for rp in remaining_problems:
            rp["_id_str"] = str(rp["_id"])

        problemas_encontrados = daily_problems_list + remaining_problems

        return render_template(
            "resultados.html",
            problemas=problemas_encontrados,
            termo_busca=""
        )

@app.route("/add", methods=["GET", "POST"])
def add_problem():
    """
    Cadastra novo problema (não resolvido), com possibilidade de adicionar tags.
    Salva também o 'creator_id' do usuário que criou.
    """
    if not user_is_logged_in():
        return redirect(url_for("index", need_login=1))

    if request.method == "POST":
        titulo = request.form.get("titulo", "").strip()
        descricao = request.form.get("descricao", "").strip()

        titulo_normalized = normalize_string(titulo)
        titulo_tokens = titulo_normalized.split()

        tags_str = request.form.get("tags", "").strip()
        user_tags_raw = tags_str.split()
        user_tags_normalized = [normalize_string(t) for t in user_tags_raw if t.strip()]

        all_tags = list(set(titulo_tokens + user_tags_normalized))

        if titulo and descricao:
            problema = {
                "titulo": titulo,
                "descricao": descricao,
                "resolvido": False,
                "tags": all_tags,
                "creator_id": session["user_id"]
            }
            problemas_collection.insert_one(problema)
            return redirect(url_for("unresolved"))
        else:
            return render_template("add.html", erro="Preencha todos os campos.")
    return render_template("add.html", erro=None)

@app.route("/unresolved", methods=["GET"])
def unresolved():
    """
    Lista problemas pendentes de solução.
    """
    if not user_is_logged_in():
        return redirect(url_for("index", need_login=1))

    query = {"resolvido": False}
    problemas_nao_resolvidos = list(problemas_collection.find(query))

    for p in problemas_nao_resolvidos:
        p["_id_str"] = str(p["_id"])
        user_creator = usuarios_collection.find_one({"_id": ObjectId(p["creator_id"])})
        p["creator_name"] = user_creator["nome"] if user_creator else "Desconhecido"

    return render_template("nao_resolvidos.html", problemas=problemas_nao_resolvidos)

@app.route("/resolver_form/<problem_id>", methods=["GET"])
def resolver_form(problem_id):
    """
    Formulário de resolução (só roles 'solucionador' ou 'mecanico').
    """
    if not user_is_logged_in():
        return redirect(url_for("index", need_login=1))
    if not user_has_role(["solucionador", "mecanico"]):
        return "Acesso negado (somente solucionadores/mecanicos).", 403

    return render_template("resolver.html", problem_id=problem_id)

@app.route("/resolver/<problem_id>", methods=["POST"])
def resolver_problema(problem_id):
    """
    Marca como resolvido, salva solucao (JSON).
    """
    if not user_is_logged_in():
        return redirect(url_for("index", need_login=1))
    if not user_has_role(["solucionador", "mecanico"]):
        return "Acesso negado (somente solucionadores/mecanicos).", 403

    solution_json = request.form.get("solution_data", "")
    try:
        solution_data = json.loads(solution_json)
    except json.JSONDecodeError:
        solution_data = {}

    problemas_collection.update_one(
        {"_id": ObjectId(problem_id)},
        {
            "$set": {
                "resolvido": True,
                "solucao": solution_data
            }
        }
    )
    return redirect(url_for("unresolved"))

@app.route("/solucao/<problem_id>", methods=["GET"])
def exibir_solucao(problem_id):
    """
    Exibe solucao de um problema resolvido.
    Registra que o user visualizou (via upsert).
    """
    if not user_is_logged_in():
        return redirect(url_for("index", need_login=1))

    problema = problemas_collection.find_one({"_id": ObjectId(problem_id)})
    if not problema:
        return "Problema não encontrado.", 404
    if not problema.get("resolvido"):
        return "Ainda não resolvido.", 400

    problem_view_history_collection.update_one(
        {"user_id": session["user_id"], "problem_id": problem_id},
        {"$set": {"user_id": session["user_id"], "problem_id": problem_id}},
        upsert=True
    )

    solucao = problema.get("solucao", {})
    return render_template("solucao.html", problema=problema, solucao=solucao)

@app.route("/delete/<problem_id>", methods=["POST"])
def delete_problem(problem_id):
    """
    Deleta problema (role 'solucionador').
    """
    if not user_is_logged_in():
        return redirect(url_for("index", need_login=1))
    if not user_has_role(["solucionador"]):
        return "Acesso negado (somente solucionador).", 403

    problema = problemas_collection.find_one({"_id": ObjectId(problem_id)})
    if not problema:
        return "Problema não encontrado.", 404

    problemas_collection.delete_one({"_id": ObjectId(problem_id)})

    if problema["resolvido"]:
        return redirect(url_for("search"))
    else:
        return redirect(url_for("unresolved"))

@app.route("/edit_problem/<problem_id>", methods=["GET", "POST"])
def edit_problem(problem_id):
    """
    Editar título/descrição/tags (só 'solucionador').
    """
    if not user_is_logged_in():
        return redirect(url_for("index", need_login=1))
    if not user_has_role(["solucionador"]):
        return "Acesso negado.", 403

    problema = problemas_collection.find_one({"_id": ObjectId(problem_id)})
    if not problema:
        return "Problema não encontrado.", 404

    if request.method == "POST":
        titulo_novo = request.form.get("titulo", "").strip()
        descricao_nova = request.form.get("descricao", "").strip()

        titulo_normalized = normalize_string(titulo_novo)
        titulo_tokens = titulo_normalized.split()

        tags_str = request.form.get("tags", "").strip()
        user_tags_raw = tags_str.split()
        user_tags_normalized = [normalize_string(t) for t in user_tags_raw if t.strip()]

        all_tags = list(set(titulo_tokens + user_tags_normalized))

        if not titulo_novo or not descricao_nova:
            erro = "Preencha todos os campos."
            return render_template("edit_problem.html", problema=problema, erro=erro)

        problemas_collection.update_one(
            {"_id": ObjectId(problem_id)},
            {
                "$set": {
                    "titulo": titulo_novo,
                    "descricao": descricao_nova,
                    "tags": all_tags
                }
            }
        )
        return redirect(url_for("search"))

    return render_template("edit_problem.html", problema=problema, erro=None)

@app.route("/edit_user_role/<user_id>", methods=["POST"])
def edit_user_role(user_id):
    """
    'solucionador' pode alterar role de outro usuário.
    """
    if not user_is_logged_in():
        return redirect(url_for("index", need_login=1))
    if not user_has_role(["solucionador"]):
        return "Acesso negado.", 403

    novo_role = request.form.get("role", "comum").strip()
    usuarios_collection.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"role": novo_role}}
    )
    return redirect(url_for("listar_usuarios"))

@app.route("/usuarios", methods=["GET"])
def listar_usuarios():
    """
    Lista todos os usuários (só 'solucionador'), com busca.
    """
    if not user_is_logged_in():
        return redirect(url_for("index", need_login=1))
    if not user_has_role(["solucionador"]):
        return "Acesso negado.", 403

    search_query = request.args.get("q", "").strip()
    if search_query:
        query = {
            "$or": [
                {"nome": {"$regex": search_query, "$options": "i"}},
                {"whatsapp": {"$regex": search_query, "$options": "i"}},
                {"maquinas": {"$regex": search_query, "$options": "i"}}
            ]
        }
    else:
        query = {}

    usuarios = list(usuarios_collection.find(query))
    for u in usuarios:
        u["_id_str"] = str(u["_id"])

    return render_template("registros.html", usuarios=usuarios, search_query=search_query)

@app.route("/delete_user/<user_id>", methods=["POST"])
def delete_user(user_id):
    """
    Deleta usuário (só 'solucionador').
    """
    if not user_is_logged_in():
        return redirect(url_for("index", need_login=1))
    if not user_has_role(["solucionador"]):
        return "Acesso negado.", 403

    usuarios_collection.delete_one({"_id": ObjectId(user_id)})
    return redirect(url_for("listar_usuarios"))

@app.route("/edit_solution/<problem_id>", methods=["GET", "POST"])
def edit_solution(problem_id):
    """
    Edição da solução de problema resolvido (somente 'solucionador'),
    incluindo upload/manutenção de imagens em GridFS.
    """
    if not user_is_logged_in():
        return redirect(url_for("index", need_login=1))
    if not user_has_role(["solucionador"]):
        return "Acesso negado.", 403

    problema = problemas_collection.find_one({"_id": ObjectId(problem_id)})
    if not problema:
        return "Problema não encontrado.", 404
    if not problema.get("resolvido"):
        return "Problema ainda não foi resolvido.", 400

    if request.method == "POST":
        new_solution_json = request.form.get("solution_data", "").strip()
        try:
            new_solution_data = json.loads(new_solution_json)
        except json.JSONDecodeError:
            erro = "Erro ao interpretar os dados."
            return render_template(
                "edit_solution.html",
                problema=problema,
                solucao=problema.get("solucao", {}),
                erro=erro
            )

        old_solution_data = problema.get("solucao", {})
        old_steps = old_solution_data.get("steps", [])
        steps = new_solution_data.get("steps", [])

        for i, step in enumerate(steps):
            # Lidar com imagem do passo
            delete_step = request.form.get(f"deleteExistingStepImage_{i}", "false") == "true"
            step_image_file = request.files.get(f"stepImage_{i}")
            new_file_id = save_image_if_exists(step_image_file)

            old_file_id = old_steps[i].get("stepImage") if i < len(old_steps) else None

            if delete_step:
                if old_file_id:
                    try:
                        fs_m.delete(ObjectId(old_file_id))
                    except:
                        pass
                step["stepImage"] = None
            elif new_file_id:
                if old_file_id:
                    try:
                        fs_m.delete(ObjectId(old_file_id))
                    except:
                        pass
                step["stepImage"] = new_file_id
            else:
                step["stepImage"] = old_file_id

            # Subpassos
            miniSteps = step.get("miniSteps", [])
            old_miniSteps = old_steps[i].get("miniSteps", []) if i < len(old_steps) else []

            for j, substep in enumerate(miniSteps):
                delete_sub = request.form.get(f"deleteExistingSubStepImage_{i}_{j}", "false") == "true"
                substep_file = request.files.get(f"subStepImage_{i}_{j}")
                new_sub_file_id = save_image_if_exists(substep_file)

                old_sub_file_id = (
                    old_miniSteps[j].get("subStepImage")
                    if j < len(old_miniSteps) else None
                )

                if delete_sub:
                    if old_sub_file_id:
                        try:
                            fs_m.delete(ObjectId(old_sub_file_id))
                        except:
                            pass
                    substep["subStepImage"] = None
                elif new_sub_file_id:
                    if old_sub_file_id:
                        try:
                            fs_m.delete(ObjectId(old_sub_file_id))
                        except:
                            pass
                    substep["subStepImage"] = new_sub_file_id
                else:
                    substep["subStepImage"] = old_sub_file_id

        problemas_collection.update_one(
            {"_id": ObjectId(problem_id)},
            {"$set": {"solucao": new_solution_data}}
        )
        return redirect(url_for("exibir_solucao", problem_id=problem_id))

    passos = problema.get("solucao", {}).get("steps", [])
    return render_template(
        "edit_solution.html",
        problema=problema,
        passos=passos,
        erro=None
    )

@app.route("/item_search", methods=["GET"])
def item_search():
    """
    Exibe a página de pesquisa de itens (DB MachineZONE).
    """
    return render_template("item_search.html")

ITEMS_PER_PAGE = 20

@app.route("/load_items", methods=["GET"])
def load_items():
    """
    Carrega itens via AJAX do banco MachineZONE, com possibilidade de busca.
    - Se 'search' estiver vazio, aplica a mesma lógica de "200 itens aleatórios do dia"
      aparecendo primeiro (em ordem embaralhada a cada carregamento) e depois
      os demais itens.
    - Se houver 'search', aplica a busca usual (com tags, matching phrases etc.).
    - Registro de histórico de pesquisa de peças (sem timestamp).
    """
    search_query = request.args.get('search', '').strip()
    page = int(request.args.get('page', 1))
    skip_items = (page - 1) * ITEMS_PER_PAGE

    # Registrar histórico (se houver algo digitado)
    if search_query:
        if user_is_logged_in():
            history_collection.insert_one({
                "user_id": session["user_id"],
                "user_name": session["username"],
                "query": search_query
            })
        else:
            history_collection.insert_one({
                "user_id": None,
                "user_name": "Guest",
                "query": search_query
            })

    # Quando não há termo, exibimos 200 itens diários + demais
    if not search_query:
        # Para fins de "scroll infinito", retornamos tudo de uma vez,
        # pois queremos primeiro os 200 diários, depois o restante.
        # Assim, a paginação no front vai simplesmente exibir blocos
        # sem reordenar.

        daily_ids = get_daily_random_items()
        # Embaralha a cada carregamento
        random.shuffle(daily_ids)

        # Busca do banco
        daily_cursor = itens_collection.find({"_id": {"$in": daily_ids}})

        daily_map = {}
        for it in daily_cursor:
            daily_map[str(it["_id"])] = it

        daily_list = []
        for did in daily_ids:
            did_str = str(did)
            if did_str in daily_map:
                daily_list.append(daily_map[did_str])

        # Carrega os demais (excluindo os daily)
        remaining_cursor = itens_collection.find({
            "_id": {"$nin": daily_ids}
        }, collation={'locale': 'pt', 'strength': 1}).sort('description', 1)
        remaining_list = list(remaining_cursor)

        # Combina
        full_list = daily_list + remaining_list

        total_items = len(full_list)
        # Pagina manualmente
        paged_items = full_list[skip_items : skip_items + ITEMS_PER_PAGE]
        has_more = (len(paged_items) == ITEMS_PER_PAGE)

        items_list = []
        for item in paged_items:
            items_list.append({
                '_id': str(item['_id']),
                'description': item.get('description', ''),
                'stock_mz': item.get('stock_mz', 0),
                'stock_eld': item.get('stock_eld', 0),
                'price': float(item.get('price', 0.0)),
                'is_highlighted': 0
            })
        return jsonify({
            'items': items_list,
            'has_more': has_more,
            'total_items': total_items
        })

    # Caso haja termo de busca, aplica pipeline
    normalized_search_phrase = normalize_string(search_query)
    search_tokens = re.findall(r'[^\s]+', normalized_search_phrase)

    phrase_match_cond = {
        '$cond': [
            {
                '$and': [
                    {'$ne': [normalized_search_phrase, ""]},
                    {'$in': [normalized_search_phrase, {'$ifNull': ['$matching_phrases', []]}]}
                ]
            },
            1,
            0
        ]
    }

    pipeline_base = [
        {
            '$addFields': {
                'is_phrase_match': phrase_match_cond
            }
        },
        {
            '$match': {
                '$or': [
                    {'is_phrase_match': 1},
                    {'tags': {'$all': search_tokens}}
                ]
            }
        }
    ]

    # Contar total
    count_pipeline = pipeline_base + [{'$count': 'total'}]
    count_result = list(itens_collection.aggregate(
        count_pipeline,
        collation={'locale': 'pt', 'strength': 1}
    ))
    total_items = count_result[0]['total'] if count_result else 0

    # Carregar matching
    items = list(itens_collection.aggregate(
        pipeline_base,
        collation={'locale': 'pt', 'strength': 1}
    ))

    # Calcular maior sub-frase
    for item in items:
        item['largest_sub_phrase_length'] = compute_largest_sub_phrase_length(
            search_tokens,
            item.get('matching_phrases', [])
        )

    # Ordena:
    # 1) Aqueles com phrase match primeiro (decrescente)
    # 2) Maior sub-frase
    # 3) Alfabético
    items.sort(
        key=lambda x: (
            -x['is_phrase_match'],
            -x['largest_sub_phrase_length'],
            x['description'].lower()
        )
    )

    # Paginação
    paged_items = items[skip_items : skip_items + ITEMS_PER_PAGE]
    has_more = (len(paged_items) == ITEMS_PER_PAGE)

    items_list = []
    for item in paged_items:
        items_list.append({
            '_id': str(item['_id']),
            'description': item.get('description', ''),
            'stock_mz': item.get('stock_mz', 0),
            'stock_eld': item.get('stock_eld', 0),
            'price': float(item.get('price', 0.0)),
            'is_highlighted': 1 if item.get('is_phrase_match') == 1 else 0
        })

    return jsonify({
        'items': items_list,
        'has_more': has_more,
        'total_items': total_items
    })

@app.route("/gridfs_image/<file_id>", methods=["GET"])
def gridfs_image(file_id):
    """
    Retorna a imagem armazenada no GridFS pelo seu ID.
    """
    try:
        gridout = fs_m.get(ObjectId(file_id))
        image_data = gridout.read()
        content_type = gridout.contentType or "image/jpeg"
        response = make_response(image_data)
        response.headers.set('Content-Type', content_type)
        return response
    except:
        return "Imagem não encontrada.", 404

@app.route("/history_search", methods=["GET"])
def history_search():
    """
    Exibe histórico de pesquisa de peças (somente 'solucionador').
    """
    if not user_is_logged_in():
        return redirect(url_for("index", need_login=1))
    if not user_has_role(["solucionador"]):
        return "Acesso negado.", 403

    all_history = list(history_collection.find({}))
    return render_template("history_search.html", history=all_history)

@app.route("/history_problem", methods=["GET"])
def history_problem():
    """
    Exibe histórico de pesquisa de problemas + sugestões de melhorias (só 'solucionador').
    """
    if not user_is_logged_in():
        return redirect(url_for("index", need_login=1))
    if not user_has_role(["solucionador"]):
        return "Acesso negado.", 403

    all_history = list(problem_history_collection.find({}))
    all_suggestions = list(improvement_suggestions_collection.find({}))

    suggestions_by_problem_dict = {}
    for s in all_suggestions:
        pid = s["problem_id"]
        if pid not in suggestions_by_problem_dict:
            suggestions_by_problem_dict[pid] = {
                "problem_title": s.get("problem_title", "Título não encontrado"),
                "suggestions": []
            }
        suggestions_by_problem_dict[pid]["suggestions"].append(s)

    suggestions_by_problem = []
    for pid, data in suggestions_by_problem_dict.items():
        suggestions_by_problem.append({
            "problem_id": pid,
            "problem_title": data["problem_title"],
            "suggestions": data["suggestions"]
        })

    return render_template(
        "history_problem.html",
        history=all_history,
        suggestions_by_problem=suggestions_by_problem
    )

@app.route("/suggest_improvement/<problem_id>", methods=["POST"])
def suggest_improvement(problem_id):
    """
    Usuário sugere melhoria na solução de um problema.
    """
    if not user_is_logged_in():
        return redirect(url_for("index", need_login=1))

    suggestion_text = request.form.get("suggestion", "").strip()
    if not suggestion_text:
        return "Texto vazio.", 400

    problem = problemas_collection.find_one({"_id": ObjectId(problem_id)})
    if not problem:
        return "Problema inexistente.", 404

    improvement_suggestions_collection.insert_one({
        "user_id": session["user_id"],
        "user_name": session["username"],
        "problem_id": str(problem["_id"]),
        "problem_title": problem["titulo"],
        "suggestion": suggestion_text,
        "submitted_at": datetime.datetime.utcnow()
    })

    return redirect(url_for("exibir_solucao", problem_id=problem_id))

@app.route("/user_history/<user_id>", methods=["GET"])
def user_history(user_id):
    """
    Histórico completo de um usuário (só 'solucionador'):
    - Problemas criados
    - Problemas visualizados
    - Histórico de pesquisa de itens
    - Histórico de pesquisa de problemas
    - Sugestões de melhoria enviadas
    """
    if not user_is_logged_in():
        return redirect(url_for("index", need_login=1))
    if not user_has_role(["solucionador"]):
        return "Acesso negado.", 403

    target_user = usuarios_collection.find_one({"_id": ObjectId(user_id)})
    if not target_user:
        return "Usuário não encontrado.", 404

    posted_problems = list(problemas_collection.find({"creator_id": user_id}))
    for p in posted_problems:
        p["_id_str"] = str(p["_id"])

    viewed_history = list(problem_view_history_collection.find({"user_id": user_id}))
    viewed_problem_ids = [vh["problem_id"] for vh in viewed_history]
    viewed_problems = list(problemas_collection.find(
        {"_id": {"$in": [ObjectId(pid) for pid in viewed_problem_ids]}}
    ))
    for vp in viewed_problems:
        vp["_id_str"] = str(vp["_id"])

    item_searches = list(history_collection.find({"user_id": user_id}))
    problem_searches = list(problem_history_collection.find({"user_id": user_id}))
    user_suggestions = list(improvement_suggestions_collection.find({"user_id": user_id}))

    return render_template(
        "history_user.html",
        target_user=target_user,
        posted_problems=posted_problems,
        viewed_problems=viewed_problems,
        item_searches=item_searches,
        problem_searches=problem_searches,
        user_suggestions=user_suggestions
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
