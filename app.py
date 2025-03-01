# app.py
import os
import json
import re
import unicodedata
import datetime
import random
import secrets
from urllib.parse import urlparse, quote
from flask import (
    Flask, render_template, request, redirect,
    url_for, session, jsonify, make_response
)
from pymongo import MongoClient
from bson.objectid import ObjectId
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
import gridfs

# ------------------------------------------------
# IMPORTAÇÃO ADICIONADA PARA TRABALHO COM IMAGENS
# ------------------------------------------------
from PIL import Image
import io

app = Flask(__name__)

# -----------------------------------------------------------
# CONFIGURAÇÃO BÁSICA
# -----------------------------------------------------------
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "CHAVE_SECRETA_PARA_SESSAO_INSEGURA")

# Evita cache de páginas, útil para conteúdo dinâmico
@app.after_request
def add_header(response):
    if request.endpoint == 'search':
        pass
    else:
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response

# -----------------------------------------------------------
# CONEXÃO COM O MONGO - BANCO M (Plataforma)
# -----------------------------------------------------------
client_m = MongoClient(
    "mongodb+srv://msolucoesmecanicasinteligentes:solucao@cluster0.7ljuh.mongodb.net/"
)
db_m = client_m["m_plataforma"]

problemas_collection = db_m["problemas"]
usuarios_collection = db_m["usuarios"]
history_collection = db_m["search_history"]
problem_history_collection = db_m["problem_search_history"]
problem_view_history_collection = db_m["problem_view_history"]
improvement_suggestions_collection = db_m["improvement_suggestions"]
step_feedback_collection = db_m["step_feedback"]
helpful_feedback_collection = db_m["helpful_feedback"]

# GridFS para armazenar imagens na plataforma M
fs_m = gridfs.GridFS(db_m)

# -----------------------------------------------------------
# CONEXÃO COM O MONGO - BANCO MachineZONE (para itens)
# -----------------------------------------------------------
client_mz = MongoClient(
    "mongodb+srv://adaltonmuzilomendes:rolamento@cluster0.atmeh.mongodb.net/"
)
db_mz = client_mz["MachineZONE"]
itens_collection = db_mz["itens"]

# GridFS para armazenar imagens de itens (MachineZONE)
fs_mz = gridfs.GridFS(db_mz)

# -----------------------------------------------------------
# CONFIGURAÇÃO E CONSTANTES
# -----------------------------------------------------------
STOPWORDS = {
    "a", "o", "de", "da", "do", "das", "dos", "em", "que", "com",
    "para", "por", "se", "e", "é", "na", "no", "nas", "nos", "as",
    "os", "um", "uma", "uns", "umas"
}

ITEMS_PER_PAGE = 20
MZ_WHATSAPP = "5543996436367"

# -----------------------------------------------------------
# FUNÇÕES AUXILIARES
# -----------------------------------------------------------
def user_is_logged_in():
    """Retorna True se há um usuário logado."""
    return "user_id" in session

def user_has_role(roles_permitidos):
    """Verifica se o usuário logado possui um dos papéis em 'roles_permitidos'."""
    if not user_is_logged_in():
        return False
    return session.get("role") in roles_permitidos

def normalize_string(s):
    """
    Remove acentos, pontuação e deixa tudo em minúsculo,
    sem espaços extras.
    """
    normalized = ''.join(
        c for c in unicodedata.normalize('NFKD', s)
        if not unicodedata.combining(c)
    )
    normalized = normalized.lower()
    normalized = re.sub(r'[^a-z0-9\s]', '', normalized)
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    return normalized

def generate_sub_phrases(tokens):
    """
    Gera todas as sub-frases contíguas de uma lista de tokens.
    Ex.: ["rolamento", "grande"] => ["rolamento", "grande", "rolamento grande"]
    """
    sub_phrases = []
    n = len(tokens)
    for start in range(n):
        for end in range(start + 1, n + 1):
            sub_slice = tokens[start:end]
            sub_phrases.append(" ".join(sub_slice))
    return sub_phrases

def compute_largest_sub_phrase_length(search_tokens, item_phrases):
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

def calculate_user_level(posted_count, solved_count):
    """
    Novo sistema de níveis:
    ---------------------------------------------------
    Nível  Nome                       Pontos   Estimativa
     1    🔧 Iniciante Curioso        0        Imediato
     2    🔩 Explorador de Engrenagens 10       2 a 4 problemas postados ou 2 resolvidos
     3    🛠 Desbravador Técnico      25       Cerca de 5 resoluções ou 10 postagens
     4    ⚙️ Mestre das Soluções      50       Cerca de 10 resoluções e algumas postagens
     5    🏆 Lenda da Mecânica        100      Cerca de 20 resoluções e engajamento geral
    ---------------------------------------------------
    Pontos = (Problemas postados * 2) + (Problemas resolvidos * 5)
    """
    points = posted_count * 2 + solved_count * 5

    if points < 10:
        level = 1
        level_name = "🔧 Iniciante Curioso"
        next_threshold = 10
        estimate_str = "Imediato"
    elif points < 25:
        level = 2
        level_name = "🔩 Explorador de Engrenagens"
        next_threshold = 25
        estimate_str = "2 a 4 problemas postados ou 2 resolvidos"
    elif points < 50:
        level = 3
        level_name = "🛠 Desbravador Técnico"
        next_threshold = 50
        estimate_str = "Cerca de 5 resoluções ou 10 postagens"
    elif points < 100:
        level = 4
        level_name = "⚙️ Mestre das Soluções"
        next_threshold = 100
        estimate_str = "Cerca de 10 resoluções e algumas postagens"
    else:
        level = 5
        level_name = "🏆 Lenda da Mecânica"
        next_threshold = 999999
        estimate_str = "Cerca de 20 resoluções e engajamento geral"

    remaining_for_next_level = max(0, next_threshold - points)

    # Cálculo do progresso dentro do nível atual:
    if level == 1:
        base_min, base_max = 0, 10
    elif level == 2:
        base_min, base_max = 10, 25
    elif level == 3:
        base_min, base_max = 25, 50
    elif level == 4:
        base_min, base_max = 50, 100
    else:
        base_min, base_max = 100, 100  # no nível máximo

    if base_max == base_min:
        progress_percentage = 100
    else:
        progress_percentage = ((points - base_min) / (base_max - base_min)) * 100
        if progress_percentage > 100:
            progress_percentage = 100

    return level, level_name, points, remaining_for_next_level, progress_percentage, estimate_str

def save_image(file_obj, fs_instance, max_w=1600, max_h=1200, thumb_w=300, thumb_h=300):
    """
    Armazena a imagem em duas versões (principal comprimida e thumbnail) no GridFS.
    Retorna um dicionário com os IDs em string {"main_id": "...", "thumb_id": "..."}
    ou None se não houver imagem válida.
    """
    if not file_obj or file_obj.filename.strip() == "":
        return None

    file_data = file_obj.read()
    if not file_data:
        return None

    try:
        # Abre a imagem original com Pillow
        img = Image.open(io.BytesIO(file_data))
    except:
        return None  # não é uma imagem válida

    # Converte para RGB
    if img.mode != 'RGB':
        img = img.convert('RGB')

    # 1) Versão principal: redimensiona até (max_w x max_h)
    img.thumbnail((max_w, max_h))
    main_io = io.BytesIO()
    # Salva em JPEG com qualidade ~80
    img.save(main_io, format='JPEG', quality=80)
    main_io.seek(0)

    main_id = fs_instance.put(
        main_io.getvalue(),
        filename=secure_filename(file_obj.filename),
        contentType='image/jpeg'
    )

    # 2) Versão thumbnail
    img_thumb = Image.open(io.BytesIO(file_data))
    if img_thumb.mode != 'RGB':
        img_thumb = img_thumb.convert('RGB')
    img_thumb.thumbnail((thumb_w, thumb_h))
    thumb_io = io.BytesIO()
    img_thumb.save(thumb_io, format='JPEG', quality=60)
    thumb_io.seek(0)

    thumb_id = fs_instance.put(
        thumb_io.getvalue(),
        filename=secure_filename("thumb_" + file_obj.filename),
        contentType='image/jpeg'
    )

    return {
        "main_id": str(main_id),
        "thumb_id": str(thumb_id)
    }

# -----------------------------------------------------------
# CRIAÇÃO DE ÍNDICE DE TEXTO (apenas se necessário)
# -----------------------------------------------------------
@app.before_first_request
def init_db():
    existing_indexes = problemas_collection.index_information()
    if "TextoProblemas" not in existing_indexes:
        problemas_collection.create_index(
            [
                ("titulo", "text"),
                ("descricao", "text"),
                ("tags", "text")
            ],
            name="TextoProblemas",
            default_language="portuguese"
        )

# -----------------------------------------------------------
# ROTAS PRINCIPAIS E DE USUÁRIOS
# -----------------------------------------------------------
@app.route("/")
def root():
    return redirect(url_for("index"))

@app.route("/index", methods=["GET", "POST"])
def index():
    backgrounds = [
        "fundo1.jpeg",
        "fundo2.png",
        "fundo3.png",
        "fundo4.png",
        "fundo5.png",
        "fundo6.jpeg"
    ]
    random_bg = random.choice(backgrounds)
    session["random_bg"] = random_bg

    if request.method == "POST":
        search_term = request.form.get("search", "").strip()
        return redirect(url_for("search", q=search_term))

    return render_template("index.html", random_bg=random_bg)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        senha = request.form.get("senha", "").strip()
        nome = " ".join(word.capitalize() for word in nome.split())

        usuario = usuarios_collection.find_one({"nome": nome})
        if usuario:
            stored_hash = usuario.get("senha_hash")
            if stored_hash:
                if check_password_hash(stored_hash, senha):
                    session["user_id"] = str(usuario["_id"])
                    session["username"] = usuario["nome"]
                    session["role"] = usuario["role"]
                    return redirect(url_for("index"))
                else:
                    return render_template("login.html", erro="Usuário ou senha inválidos.")
            else:
                # Fallback (sem hash) -> migra para hash
                if usuario.get("senha") == senha:
                    new_hash = generate_password_hash(senha)
                    usuarios_collection.update_one(
                        {"_id": usuario["_id"]},
                        {"$set": {"senha_hash": new_hash}, "$unset": {"senha": ""}}
                    )
                    session["user_id"] = str(usuario["_id"])
                    session["username"] = usuario["nome"]
                    session["role"] = usuario["role"]
                    return redirect(url_for("index"))
                else:
                    return render_template("login.html", erro="Usuário ou senha inválidos.")
        else:
            return render_template("login.html", erro="Usuário ou senha inválidos.")

    return render_template("login.html", erro=None)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

@app.route("/register", methods=["GET", "POST"])
def register():
    raw_next = request.args.get("next", "")
    parsed = urlparse(raw_next)
    if parsed.path:
        next_url = parsed.path + (("?" + parsed.query) if parsed.query else "")
    else:
        next_url = ""

    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        senha = request.form.get("senha", "").strip()
        confirmar_senha = request.form.get("confirmar_senha", "").strip()
        whatsapp = request.form.get("whatsapp", "").strip()
        maquinas = request.form.get("maquinas", "").strip()

        if senha != confirmar_senha:
            return render_template("register.html", erro="As senhas não conferem!", next_url=next_url)

        nome = " ".join(word.capitalize() for word in nome.split())
        if usuarios_collection.find_one({"nome": nome}):
            return render_template("register.html", erro="Usuário já existe!", next_url=next_url)

        senha_hash = generate_password_hash(senha)
        novo_usuario = {
            "nome": nome,
            "senha_hash": senha_hash,
            "role": "comum",
            "whatsapp": whatsapp,
            "maquinas": maquinas,
            "profile_image_id": None,
            "perfil_token": None
        }
        inserted = usuarios_collection.insert_one(novo_usuario)

        session["user_id"] = str(inserted.inserted_id)
        session["username"] = nome
        session["role"] = "comum"

        if next_url:
            return redirect(next_url)
        else:
            return redirect(url_for("index"))

    return render_template("register.html", erro=None, next_url=next_url)

# -----------------------------------------------------------
# ROTAS LIGADAS A PROBLEMAS
# -----------------------------------------------------------
@app.route("/search", methods=["GET"])
def search():
    termo_busca = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()
    subcategory = request.args.get("subcategory", "").strip()
    brand = request.args.get("brand", "").strip()

    random_bg = session.get("random_bg", "fundo1.jpeg")

    return render_template(
        "resultados.html",
        termo_busca=termo_busca,
        selected_category=category,
        selected_subcategory=subcategory,
        selected_brand=brand,
        random_bg=random_bg
    )

@app.route("/load_problems", methods=["GET"])
def load_problems():
    search_query = request.args.get("q", "").strip()
    page = int(request.args.get("page", 1))

    category = request.args.get("category", "").strip()
    subcategory = request.args.get("subcategory", "").strip()
    brand = request.args.get("brand", "").strip()

    # Força somente problemas resolvidos
    filters = {"resolvido": True}

    if category:
        filters["category"] = category
    if subcategory:
        filters["subCategory"] = subcategory
    if brand:
        filters["brand"] = brand

    if search_query:
        if user_is_logged_in():
            problem_history_collection.insert_one({
                "user_id": session["user_id"],
                "user_name": session["username"],
                "query": search_query,
                "searched_at": datetime.datetime.utcnow()
            })
        else:
            problem_history_collection.insert_one({
                "user_id": None,
                "user_name": "Guest",
                "query": search_query,
                "searched_at": datetime.datetime.utcnow()
            })

        search_tokens = [t for t in normalize_string(search_query).split() if t and t not in STOPWORDS]
        if search_tokens:
            skip = (page - 1) * ITEMS_PER_PAGE
            match_stage = {"$and": [{"tags": {"$all": search_tokens}}]}

            for key, val in filters.items():
                match_stage["$and"].append({key: val})

            count_pipeline = [{"$match": match_stage}, {"$count": "total"}]
            count_result = list(problemas_collection.aggregate(count_pipeline))
            total_count = count_result[0]["total"] if count_result else 0

            pipeline_fetch = [
                {"$match": match_stage},
                {"$skip": skip},
                {"$limit": ITEMS_PER_PAGE}
            ]
            problems_cursor = problemas_collection.aggregate(pipeline_fetch)
            problems = list(problems_cursor)

            problems_list = []
            for p in problems:
                # Criador
                if p.get("creator_custom_name"):
                    creator_name = p["creator_custom_name"]
                    creator_profile_image_id = None
                else:
                    creator_name = "Não definido"
                    creator_profile_image_id = None
                    if p.get("creator_id"):
                        c_user = usuarios_collection.find_one({"_id": ObjectId(p["creator_id"])})
                        if c_user:
                            creator_name = c_user["nome"]
                            creator_profile_image_id = c_user.get("profile_image_id")

                # Solucionador
                solver_name = None
                solver_profile_image_id = None
                if p.get("solver_custom_name"):
                    solver_name = p["solver_custom_name"]
                else:
                    if p.get("solver_id"):
                        s_user = usuarios_collection.find_one({"_id": ObjectId(p["solver_id"])})
                        if s_user:
                            solver_name = s_user["nome"]
                            solver_profile_image_id = s_user.get("profile_image_id")

                problems_list.append({
                    "_id": str(p["_id"]),
                    "titulo": p.get("titulo", ""),
                    "descricao": p.get("descricao", ""),
                    "resolvido": p.get("resolvido", False),
                    "problemImage_main": str(p["problemImage_main"]) if p.get("problemImage_main") else None,
                    "problemImage_thumb": str(p["problemImage_thumb"]) if p.get("problemImage_thumb") else None,
                    "creator_name": creator_name,
                    "creator_profile_image_id": creator_profile_image_id,
                    "solver_name": solver_name,
                    "solver_profile_image_id": solver_profile_image_id,
                    "creator_id": str(p["creator_id"]) if p.get("creator_id") else None,
                    "solver_id": str(p["solver_id"]) if p.get("solver_id") else None,
                    "category": p.get("category", ""),
                    "subCategory": p.get("subCategory", ""),
                    "brand": p.get("brand", "")
                })

            has_more = (skip + ITEMS_PER_PAGE) < total_count
            return jsonify({"problems": problems_list, "has_more": has_more, "total_count": total_count})

        else:
            return jsonify({"problems": [], "has_more": False, "total_count": 0})

    else:
        # Busca vazia -> problemas aleatórios (somente resolvidos)
        if page == 1:
            session["displayed_problem_ids"] = []
        displayed_ids = session.get("displayed_problem_ids", [])
        displayed_object_ids = [ObjectId(x) for x in displayed_ids]

        random_match_stage = {"_id": {"$nin": displayed_object_ids}}
        for key, val in filters.items():
            random_match_stage[key] = val

        pipeline_count = [{"$match": random_match_stage}, {"$count": "remaining_count"}]
        count_res = list(problemas_collection.aggregate(pipeline_count))
        remaining_count = count_res[0]["remaining_count"] if count_res else 0

        if remaining_count <= 0:
            return jsonify({"problems": [], "has_more": False, "total_count": 0})
        else:
            fetch_size = min(ITEMS_PER_PAGE, remaining_count)
            pipeline_sample = [
                {"$match": random_match_stage},
                {"$sample": {"size": fetch_size}}
            ]
            cursor_sample = problemas_collection.aggregate(pipeline_sample)
            random_problems = list(cursor_sample)

            for rp in random_problems:
                displayed_ids.append(str(rp["_id"]))
            session["displayed_problem_ids"] = displayed_ids

            has_more = (remaining_count - fetch_size) > 0
            problems_list = []
            for p in random_problems:
                if p.get("creator_custom_name"):
                    creator_name = p["creator_custom_name"]
                    creator_profile_image_id = None
                else:
                    creator_name = "Não definido"
                    creator_profile_image_id = None
                    if p.get("creator_id"):
                        c_user = usuarios_collection.find_one({"_id": ObjectId(p["creator_id"])})
                        if c_user:
                            creator_name = c_user["nome"]
                            creator_profile_image_id = c_user.get("profile_image_id")

                solver_name = None
                solver_profile_image_id = None
                if p.get("solver_custom_name"):
                    solver_name = p["solver_custom_name"]
                else:
                    if p.get("solver_id"):
                        s_user = usuarios_collection.find_one({"_id": ObjectId(p["solver_id"])})
                        if s_user:
                            solver_name = s_user["nome"]
                            solver_profile_image_id = s_user.get("profile_image_id")

                problems_list.append({
                    "_id": str(p["_id"]),
                    "titulo": p.get("titulo", ""),
                    "descricao": p.get("descricao", ""),
                    "resolvido": p.get("resolvido", False),
                    "problemImage_main": str(p["problemImage_main"]) if p.get("problemImage_main") else None,
                    "problemImage_thumb": str(p["problemImage_thumb"]) if p.get("problemImage_thumb") else None,
                    "creator_name": creator_name,
                    "creator_profile_image_id": creator_profile_image_id,
                    "solver_name": solver_name,
                    "solver_profile_image_id": solver_profile_image_id,
                    "creator_id": str(p["creator_id"]) if p.get("creator_id") else None,
                    "solver_id": str(p["solver_id"]) if p.get("solver_id") else None,
                    "category": p.get("category", ""),
                    "subCategory": p.get("subCategory", ""),
                    "brand": p.get("brand", "")
                })

            return jsonify({
                "problems": problems_list,
                "has_more": has_more,
                "total_count": remaining_count
            })

@app.route("/add", methods=["GET", "POST"])
def add_problem():
    if not user_is_logged_in():
        return redirect(url_for("register", next=request.url))

    if request.method == "POST":
        titulo = request.form.get("titulo", "").strip()
        descricao = request.form.get("descricao", "").strip()

        titulo_normalized = normalize_string(titulo)
        titulo_tokens = [t for t in titulo_normalized.split() if t not in STOPWORDS]
        all_tags = list(set(titulo_tokens))

        category = request.form.get("category", "").strip()
        subCategory = request.form.get("subCategory", "").strip()
        brand = request.form.get("brand", "").strip()

        image_file = request.files.get("problemImage")
        image_ids = save_image(image_file, fs_m)

        if titulo and descricao:
            if image_ids:
                main_id = image_ids["main_id"]
                thumb_id = image_ids["thumb_id"]
            else:
                main_id = None
                thumb_id = None

            problema = {
                "titulo": titulo,
                "descricao": descricao,
                "resolvido": False,
                "tags": all_tags,
                "creator_id": session["user_id"],
                "creator_custom_name": None,
                "solver_id": None,
                "solver_custom_name": None,
                "problemImage_main": main_id,
                "problemImage_thumb": thumb_id,
                "category": category,
                "subCategory": subCategory,
                "brand": brand
            }
            problemas_collection.insert_one(problema)
            return redirect(url_for("unresolved"))
        else:
            return render_template("add.html", erro="Preencha todos os campos.")

    return render_template("add.html", erro=None)

@app.route("/unresolved", methods=["GET"])
def unresolved():
    if not user_is_logged_in():
        return redirect(url_for("register", next=request.url))

    referrer = request.referrer
    if referrer and "resolver" not in referrer and "unresolved" not in referrer:
        session["nao_resolvidos_prev_page"] = referrer

    query = {"resolvido": False}
    problemas_nao_resolvidos = list(problemas_collection.find(query))
    for p in problemas_nao_resolvidos:
        p["_id_str"] = str(p["_id"])
        if p.get("creator_custom_name"):
            p["creator_name"] = p["creator_custom_name"]
        else:
            c_user = None
            if p.get("creator_id"):
                c_user = usuarios_collection.find_one({"_id": ObjectId(p["creator_id"])})
            p["creator_name"] = c_user["nome"] if c_user else "Desconhecido"

    return render_template("nao_resolvidos.html", problemas=problemas_nao_resolvidos)

@app.route("/resolver_form/<problem_id>", methods=["GET"])
def resolver_form(problem_id):
    if not user_is_logged_in():
        return redirect(url_for("register", next=request.url))

    problem = problemas_collection.find_one({"_id": ObjectId(problem_id)})
    if not problem:
        return "Problema não encontrado.", 404

    if problem.get("creator_custom_name"):
        creator_name = problem["creator_custom_name"]
    else:
        creator_name = "Desconhecido"
        if problem.get("creator_id"):
            c_user = usuarios_collection.find_one({"_id": ObjectId(problem["creator_id"])})
            if c_user:
                creator_name = c_user["nome"]

    return render_template("resolver.html", problem=problem, creator_name=creator_name)

@app.route("/resolver/<problem_id>", methods=["POST"])
def resolver_problema(problem_id):
    if not user_is_logged_in():
        return redirect(url_for("register", next=request.url))

    solution_json = request.form.get("solution_data", "")
    try:
        solution_data = json.loads(solution_json)
    except json.JSONDecodeError:
        solution_data = {}

    steps = solution_data.get("steps")
    if not steps or len(steps) == 0:
        return "Não é possível enviar uma solução vazia. Volte e adicione pelo menos um passo.", 400

    # Upload de imagens dos passos e subpassos
    for i, step in enumerate(steps):
        step_file = request.files.get(f"stepImage_{i}")
        if step_file and step_file.filename.strip():
            image_ids = save_image(step_file, fs_m)
            if image_ids:
                step["stepImage"] = image_ids["main_id"]

        miniSteps = step.get("miniSteps", [])
        for j, substep in enumerate(miniSteps):
            sub_file = request.files.get(f"subStepImage_{i}_{j}")
            if sub_file and sub_file.filename.strip():
                image_ids = save_image(sub_file, fs_m)
                if image_ids:
                    substep["subStepImage"] = image_ids["main_id"]

    # Marca como resolvido
    problemas_collection.update_one(
        {"_id": ObjectId(problem_id)},
        {
            "$set": {
                "resolvido": True,
                "solucao": solution_data,
                "solver_id": session["user_id"],
                "solver_custom_name": None
            }
        }
    )
    return redirect(url_for("unresolved"))

@app.route("/solucao/<problem_id>", methods=["GET"])
def exibir_solucao(problem_id):
    problema = problemas_collection.find_one({"_id": ObjectId(problem_id)})
    if not problema:
        return "Problema não encontrado.", 404
    if not problema.get("resolvido"):
        return "Ainda não resolvido.", 400

    # Gera token para compartilhamento, se não existir
    if "share_token" not in problema:
        new_token = secrets.token_urlsafe(16)
        problemas_collection.update_one(
            {"_id": ObjectId(problem_id)},
            {"$set": {"share_token": new_token}}
        )
        problema["share_token"] = new_token

    # Verifica login ou token
    token_param = request.args.get("token", "")
    if not user_is_logged_in() and token_param != problema["share_token"]:
        return redirect(url_for("register", next=request.url))

    # Registra visualização se logado
    if user_is_logged_in():
        problem_view_history_collection.update_one(
            {"user_id": session["user_id"], "problem_id": problem_id},
            {"$set": {"user_id": session["user_id"], "problem_id": problem_id}},
            upsert=True
        )

    # Criador
    if problema.get("creator_custom_name"):
        creator_name = problema["creator_custom_name"]
        creator_id = None
        creator_profile_image_id = None
    else:
        creator_name = "Desconhecido"
        creator_id = problema.get("creator_id")
        creator_profile_image_id = None
        if creator_id:
            c_user = usuarios_collection.find_one({"_id": ObjectId(creator_id)})
            if c_user:
                creator_name = c_user["nome"]
                creator_profile_image_id = c_user.get("profile_image_id")

    # Solucionador
    if problema.get("solver_custom_name"):
        solver_name = problema["solver_custom_name"]
        solver_id = None
        solver_profile_image_id = None
    else:
        solver_name = "Desconhecido"
        solver_id = problema.get("solver_id")
        solver_profile_image_id = None
        if solver_id:
            s_user = usuarios_collection.find_one({"_id": ObjectId(solver_id)})
            if s_user:
                solver_name = s_user["nome"]
                solver_profile_image_id = s_user.get("profile_image_id")

    solucao = problema.get("solucao", {})
    share_url = url_for("exibir_solucao", problem_id=problem_id, token=problema["share_token"], _external=True)
    share_text = f"Confira a solução para: {problema['titulo']} - {share_url}"
    share_msg_encoded = quote(share_text, safe='')

    user_helpful_feedback = None
    if user_is_logged_in():
        existing_feedback = helpful_feedback_collection.find_one({
            "problem_id": problem_id,
            "user_id": session["user_id"]
        })
        if existing_feedback:
            user_helpful_feedback = existing_feedback.get("feedback")

    like_count = helpful_feedback_collection.count_documents({
        "problem_id": problem_id,
        "feedback": "SIM"
    })

    random_bg = session.get("random_bg", "fundo1.jpeg")

    return render_template(
        "solucao.html",
        problema=problema,
        solucao=solucao,
        share_msg_encoded=share_msg_encoded,
        creator_name=creator_name,
        solver_name=solver_name,
        creator_id=creator_id,
        solver_id=solver_id,
        creator_profile_image_id=creator_profile_image_id,
        solver_profile_image_id=solver_profile_image_id,
        user_helpful_feedback=user_helpful_feedback,
        like_count=like_count,
        random_bg=random_bg
    )

@app.route("/delete/<problem_id>", methods=["POST"])
def delete_problem(problem_id):
    if not user_is_logged_in():
        return redirect(url_for("register", next=request.url))
    if not user_has_role(["solucionador"]):
        return "Acesso negado (somente solucionador).", 403

    problema = problemas_collection.find_one({"_id": ObjectId(problem_id)})
    if not problema:
        return "Problema não encontrado.", 404

    old_main_id = problema.get("problemImage_main")
    old_thumb_id = problema.get("problemImage_thumb")
    if old_main_id:
        try:
            fs_m.delete(ObjectId(old_main_id))
        except:
            pass
    if old_thumb_id:
        try:
            fs_m.delete(ObjectId(old_thumb_id))
        except:
            pass

    problemas_collection.delete_one({"_id": ObjectId(problem_id)})

    if problema["resolvido"]:
        return redirect(url_for("search"))
    else:
        return redirect(url_for("unresolved"))

@app.route("/edit_problem/<problem_id>", methods=["GET", "POST"])
def edit_problem(problem_id):
    if not user_is_logged_in():
        return redirect(url_for("register", next=request.url))

    problema = problemas_collection.find_one({"_id": ObjectId(problem_id)})
    if not problema:
        return "Problema não encontrado.", 404

    can_edit = (session["user_id"] == problema.get("creator_id")) or user_has_role(["solucionador"])
    if not can_edit:
        return "Acesso negado.", 403

    all_users = list(usuarios_collection.find({}, {"_id": 1, "nome": 1}))

    if request.method == "POST":
        titulo_novo = request.form.get("titulo", "").strip()
        descricao_nova = request.form.get("descricao", "").strip()

        category = request.form.get("category", "").strip()
        subCategory = request.form.get("subCategory", "").strip()
        brand = request.form.get("brand", "").strip()

        creator_id = request.form.get("creator_id", "")
        creator_custom_name = request.form.get("creator_custom_name", "").strip()
        solver_id = request.form.get("solver_id", "")
        solver_custom_name = request.form.get("solver_custom_name", "").strip()

        tags_raw = request.form.get("tags", "").strip()
        tags_normalized = normalize_string(tags_raw)
        tags_tokens = [t for t in tags_normalized.split() if t and t not in STOPWORDS]

        if solver_id in ("", "None"):
            solver_id = None
        if creator_id in ("", "None"):
            creator_id = None

        if not titulo_novo or not descricao_nova:
            return render_template(
                "edit_problem.html",
                problema=problema,
                erro="Preencha todos os campos.",
                all_users=all_users
            )

        if creator_id == "custom":
            final_creator_id = None
            final_creator_name = creator_custom_name
        else:
            final_creator_id = creator_id
            final_creator_name = None

        if solver_id == "custom":
            final_solver_id = None
            final_solver_name = solver_custom_name
        else:
            final_solver_id = solver_id
            final_solver_name = None

        old_tags = problema.get("tags", [])
        titulo_normalizado = normalize_string(titulo_novo)
        descricao_normalizado = normalize_string(descricao_nova)

        titulo_tokens = [t for t in titulo_normalizado.split() if t and t not in STOPWORDS]
        descricao_tokens = [t for t in descricao_normalizado.split() if t and t not in STOPWORDS]

        final_tag_set = set(old_tags) | set(tags_tokens) | set(titulo_tokens) | set(descricao_tokens)
        final_tags = list(final_tag_set)

        updated_fields = {
            "titulo": titulo_novo,
            "descricao": descricao_nova,
            "tags": final_tags,
            "creator_id": final_creator_id,
            "creator_custom_name": final_creator_name,
            "solver_id": final_solver_id,
            "solver_custom_name": final_solver_name,
            "category": category,
            "subCategory": subCategory,
            "brand": brand
        }

        delete_image = request.form.get("deleteExistingImage", "false") == "true"
        image_file = request.files.get("problemImage")

        if delete_image:
            old_main_id = problema.get("problemImage_main")
            old_thumb_id = problema.get("problemImage_thumb")
            if old_main_id:
                try:
                    fs_m.delete(ObjectId(old_main_id))
                except:
                    pass
            if old_thumb_id:
                try:
                    fs_m.delete(ObjectId(old_thumb_id))
                except:
                    pass
            updated_fields["problemImage_main"] = None
            updated_fields["problemImage_thumb"] = None
        elif image_file and image_file.filename.strip():
            image_ids = save_image(image_file, fs_m)
            if image_ids:
                new_main_id = image_ids["main_id"]
                new_thumb_id = image_ids["thumb_id"]
                old_main_id = problema.get("problemImage_main")
                old_thumb_id = problema.get("problemImage_thumb")
                if old_main_id:
                    try:
                        fs_m.delete(ObjectId(old_main_id))
                    except:
                        pass
                if old_thumb_id:
                    try:
                        fs_m.delete(ObjectId(old_thumb_id))
                    except:
                        pass
                updated_fields["problemImage_main"] = new_main_id
                updated_fields["problemImage_thumb"] = new_thumb_id

        problemas_collection.update_one(
            {"_id": ObjectId(problem_id)},
            {"$set": updated_fields}
        )
        return redirect(url_for("search", q=titulo_novo))

    return render_template("edit_problem.html", problema=problema, erro=None, all_users=all_users)

@app.route("/edit_your_problem/<problem_id>", methods=["GET", "POST"])
def edit_your_problem(problem_id):
    if not user_is_logged_in():
        return redirect(url_for("register", next=request.url))

    problema = problemas_collection.find_one({"_id": ObjectId(problem_id)})
    if not problema:
        return "Problema não encontrado.", 404

    if problema.get("resolvido", False):
        return "Este problema já foi resolvido. Use a rota de edição geral.", 400

    can_edit = (session["user_id"] == problema.get("creator_id")) or user_has_role(["solucionador"])
    if not can_edit:
        return "Acesso negado. Somente o criador ou um solucionador podem editar.", 403

    if request.method == "POST":
        titulo_novo = request.form.get("titulo", "").strip()
        descricao_nova = request.form.get("descricao", "").strip()

        category = request.form.get("category", "").strip()
        subCategory = request.form.get("subCategory", "").strip()
        brand = request.form.get("brand", "").strip()

        tags_raw = request.form.get("tags", "").strip()
        tags_normalized = normalize_string(tags_raw)
        tags_tokens = [t for t in tags_normalized.split() if t and t not in STOPWORDS]

        if not titulo_novo or not descricao_nova:
            return render_template(
                "edit_your_problem.html",
                problema=problema,
                erro="Preencha todos os campos."
            )

        old_solver_id = problema.get("solver_id")
        old_solver_custom_name = problema.get("solver_custom_name")

        old_tags = problema.get("tags", [])
        titulo_normalizado = normalize_string(titulo_novo)
        descricao_normalizado = normalize_string(descricao_nova)

        titulo_tokens = [t for t in titulo_normalizado.split() if t and t not in STOPWORDS]
        descricao_tokens = [t for t in descricao_normalizado.split() if t and t not in STOPWORDS]

        final_tag_set = set(old_tags) | set(tags_tokens) | set(titulo_tokens) | set(descricao_tokens)
        final_tags = list(final_tag_set)

        updated_fields = {
            "titulo": titulo_novo,
            "descricao": descricao_nova,
            "tags": final_tags,
            "category": category,
            "subCategory": subCategory,
            "brand": brand
        }

        delete_image = request.form.get("deleteExistingImage", "false") == "true"
        image_file = request.files.get("problemImage")

        if delete_image:
            old_main_id = problema.get("problemImage_main")
            old_thumb_id = problema.get("problemImage_thumb")
            if old_main_id:
                try:
                    fs_m.delete(ObjectId(old_main_id))
                except:
                    pass
            if old_thumb_id:
                try:
                    fs_m.delete(ObjectId(old_thumb_id))
                except:
                    pass
            updated_fields["problemImage_main"] = None
            updated_fields["problemImage_thumb"] = None
        elif image_file and image_file.filename.strip():
            image_ids = save_image(image_file, fs_m)
            if image_ids:
                new_main_id = image_ids["main_id"]
                new_thumb_id = image_ids["thumb_id"]
                old_main_id = problema.get("problemImage_main")
                old_thumb_id = problema.get("problemImage_thumb")
                if old_main_id:
                    try:
                        fs_m.delete(ObjectId(old_main_id))
                    except:
                        pass
                if old_thumb_id:
                    try:
                        fs_m.delete(ObjectId(old_thumb_id))
                    except:
                        pass
                updated_fields["problemImage_main"] = new_main_id
                updated_fields["problemImage_thumb"] = new_thumb_id

        if old_solver_id:
            updated_fields["solver_id"] = old_solver_id
        if old_solver_custom_name:
            updated_fields["solver_custom_name"] = old_solver_custom_name

        problemas_collection.update_one(
            {"_id": ObjectId(problem_id)},
            {"$set": updated_fields}
        )
        return redirect(url_for("unresolved"))

    return render_template("edit_your_problem.html", problema=problema, erro=None)

@app.route("/edit_user_role/<user_id>", methods=["POST"])
def edit_user_role(user_id):
    if not user_is_logged_in():
        return redirect(url_for("register", next=request.url))
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
    if not user_is_logged_in():
        return redirect(url_for("register", next=request.url))
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
    if not user_is_logged_in():
        return redirect(url_for("register", next=request.url))
    if not user_has_role(["solucionador"]):
        return "Acesso negado.", 403

    usuarios_collection.delete_one({"_id": ObjectId(user_id)})
    return redirect(url_for("listar_usuarios"))

@app.route("/edit_solution/<problem_id>", methods=["GET", "POST"])
def edit_solution(problem_id):
    if not user_is_logged_in():
        return redirect(url_for("register", next=request.url))
    if not user_has_role(["solucionador"]):
        return "Acesso negado.", 403

    problema = problemas_collection.find_one({"_id": ObjectId(problem_id)})
    if not problema:
        return "Problema não encontrado.", 404
    if not problema.get("resolvido"):
        return "Ainda não resolvido.", 400

    if request.method == "POST":
        new_solution_json = request.form.get("solution_data", "").strip()
        try:
            new_solution_data = json.loads(new_solution_json)
        except json.JSONDecodeError:
            return render_template(
                "edit_solution.html",
                problema=problema,
                passos=problema.get("solucao", {}).get("steps", []),
                erro="Erro ao interpretar os dados."
            )

        old_solution_data = problema.get("solucao", {})
        old_steps = old_solution_data.get("steps", [])
        steps = new_solution_data.get("steps", [])

        for i, step in enumerate(steps):
            delete_step = request.form.get(f"deleteExistingStepImage_{i}", "false") == "true"
            step_image_file = request.files.get(f"stepImage_{i}")

            old_file_id = None
            if i < len(old_steps):
                old_file_id = old_steps[i].get("stepImage")

            if delete_step and old_file_id:
                try:
                    fs_m.delete(ObjectId(old_file_id))
                except:
                    pass
                step["stepImage"] = None
            elif step_image_file and step_image_file.filename.strip():
                image_ids = save_image(step_image_file, fs_m, max_w=1200, max_h=1200, thumb_w=300, thumb_h=300)
                if image_ids:
                    if old_file_id:
                        try:
                            fs_m.delete(ObjectId(old_file_id))
                        except:
                            pass
                    step["stepImage"] = image_ids["main_id"]
            else:
                step["stepImage"] = old_file_id

            miniSteps = step.get("miniSteps", [])
            old_miniSteps = old_steps[i].get("miniSteps", []) if i < len(old_steps) else []

            for j, substep in enumerate(miniSteps):
                delete_sub = request.form.get(f"deleteExistingSubStepImage_{i}_{j}", "false") == "true"
                substep_file = request.files.get(f"subStepImage_{i}_{j}")

                old_sub_file_id = None
                if j < len(old_miniSteps):
                    old_sub_file_id = old_miniSteps[j].get("subStepImage")

                if delete_sub and old_sub_file_id:
                    try:
                        fs_m.delete(ObjectId(old_sub_file_id))
                    except:
                        pass
                    substep["subStepImage"] = None
                elif substep_file and substep_file.filename.strip():
                    sub_image_ids = save_image(substep_file, fs_m, max_w=1200, max_h=1200, thumb_w=300, thumb_h=300)
                    if sub_image_ids:
                        if old_sub_file_id:
                            try:
                                fs_m.delete(ObjectId(old_sub_file_id))
                            except:
                                pass
                        substep["subStepImage"] = sub_image_ids["main_id"]
                else:
                    substep["subStepImage"] = old_sub_file_id

        problemas_collection.update_one(
            {"_id": ObjectId(problem_id)},
            {"$set": {"solucao": new_solution_data}}
        )
        return redirect(url_for("exibir_solucao", problem_id=problem_id))

    passos = problema.get("solucao", {}).get("steps", [])
    return render_template("edit_solution.html", problema=problema, passos=passos, erro=None)

# -----------------------------------------------------------
# GRIDFS - EXIBIÇÃO DE IMAGENS (PROBLEMAS)
# -----------------------------------------------------------
@app.route("/gridfs_image/<file_id>", methods=["GET"])
def gridfs_image(file_id):
    try:
        gridout = fs_m.get(ObjectId(file_id))
        image_data = gridout.read()
        content_type = gridout.contentType or "image/jpeg"
        response = make_response(image_data)
        response.headers.set('Content-Type', content_type)
        return response
    except:
        return "Imagem não encontrada.", 404

# -----------------------------------------------------------
# GRIDFS - IMAGENS (ITENS) - MachineZONE
# -----------------------------------------------------------
@app.route("/gridfs_item_image/<file_id>", methods=["GET"])
def gridfs_item_image(file_id):
    try:
        gridout = fs_mz.get(ObjectId(file_id))
        image_data = gridout.read()
        content_type = gridout.contentType or "image/jpeg"
        response = make_response(image_data)
        response.headers.set('Content-Type', content_type)
        return response
    except:
        return "Imagem do item não encontrada.", 404

# -----------------------------------------------------------
# HISTÓRICOS
# -----------------------------------------------------------
@app.route("/history_search", methods=["GET"])
def history_search():
    if not user_is_logged_in():
        return redirect(url_for("register", next=request.url))
    if not user_has_role(["solucionador"]):
        return "Acesso negado.", 403

    all_history = list(history_collection.find({}))
    return render_template("history_search.html", history=all_history)

@app.route("/history_problem", methods=["GET"])
def history_problem():
    if not user_is_logged_in():
        return redirect(url_for("register", next=request.url))
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
    if not user_is_logged_in():
        return "Texto vazio.", 400

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
    if not user_is_logged_in():
        return redirect(url_for("register", next=request.url))
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
    viewed_problems = list(
        problemas_collection.find({"_id": {"$in": [ObjectId(pid) for pid in viewed_problem_ids]}})
    )
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

# -----------------------------------------------------------
# PESQUISA DE ITENS (MachineZONE) + Upload
# -----------------------------------------------------------
@app.route("/item_search", methods=["GET"])
def item_search():
    return render_template("item_search.html")

@app.route("/load_items", methods=["GET"])
def load_items():
    search_query = request.args.get('search', '').strip()
    page = int(request.args.get('page', 1))

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

        skip_items = (page - 1) * ITEMS_PER_PAGE
        normalized_search_phrase = normalize_string(search_query)
        search_tokens = [t for t in normalized_search_phrase.split() if t and t not in STOPWORDS]

        pipeline_base = [
            {
                '$addFields': {
                    'matching_phrases': '$matching_phrases'
                }
            },
            {
                '$addFields': {
                    'is_phrase_match': {
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

        count_pipeline = pipeline_base + [{'$count': 'total'}]
        count_result = list(itens_collection.aggregate(
            count_pipeline,
            collation={'locale': 'pt', 'strength': 1}
        ))
        total_items = count_result[0]['total'] if count_result else 0

        items_cursor = itens_collection.aggregate(
            pipeline_base,
            collation={'locale': 'pt', 'strength': 1}
        )
        items = list(items_cursor)

        for item in items:
            item['largest_sub_phrase_length'] = compute_largest_sub_phrase_length(
                search_tokens,
                item.get('matching_phrases', [])
            )

        items.sort(
            key=lambda x: (
                -x['is_phrase_match'],
                -x['largest_sub_phrase_length'],
                x['description'].lower()
            )
        )
        paged_items = items[skip_items: skip_items + ITEMS_PER_PAGE]
        has_more = (len(paged_items) == ITEMS_PER_PAGE and (skip_items + ITEMS_PER_PAGE) < len(items))

        items_list = []
        for it in paged_items:
            items_list.append({
                '_id': str(it['_id']),
                'description': it.get('description', ''),
                'stock_mz': it.get('stock_mz', 0),
                'stock_eld': it.get('stock_eld', 0),
                'price': float(it.get('price', 0.0)),
                'is_highlighted': 1 if it.get('is_phrase_match') == 1 else 0,
                'itemImage_main': str(it['itemImage_main']) if it.get('itemImage_main') else None,
                'itemImage_thumb': str(it['itemImage_thumb']) if it.get('itemImage_thumb') else None
            })

        return jsonify({
            'items': items_list,
            'has_more': has_more,
            'total_items': total_items
        })
    else:
        if page == 1:
            session["displayed_item_ids"] = []
        displayed_ids = session.get("displayed_item_ids", [])
        displayed_objectids = [ObjectId(x) for x in displayed_ids]

        pipeline_count = [
            {"$match": {"_id": {"$nin": displayed_objectids}}},
            {"$count": "remaining_count"}
        ]
        count_res = list(itens_collection.aggregate(pipeline_count))
        remaining_count = count_res[0]["remaining_count"] if count_res else 0

        if remaining_count <= 0:
            items = []
            has_more = False
        else:
            fetch_size = min(ITEMS_PER_PAGE, remaining_count)
            pipeline_sample = [
                {"$match": {"_id": {"$nin": displayed_objectids}}},
                {"$sample": {"size": fetch_size}}
            ]
            items_cursor = itens_collection.aggregate(pipeline_sample)
            items = list(items_cursor)

            for it in items:
                displayed_ids.append(str(it["_id"]))
            session["displayed_item_ids"] = displayed_ids
            has_more = (remaining_count - fetch_size) > 0

        response_items = []
        for it in items:
            response_items.append({
                '_id': str(it['_id']),
                'description': it.get('description', ''),
                'stock_mz': it.get('stock_mz', 0),
                'stock_eld': it.get('stock_eld', 0),
                'price': float(it.get('price', 0.0)),
                'itemImage_main': str(it['itemImage_main']) if it.get('itemImage_main') else None,
                'itemImage_thumb': str(it['itemImage_thumb']) if it.get('itemImage_thumb') else None
            })

        return jsonify({
            "items": response_items,
            "has_more": has_more,
            "total_items": remaining_count
        })

@app.route("/upload_item_image/<item_id>", methods=["POST"])
def upload_item_image(item_id):
    if not user_is_logged_in():
        return redirect(url_for("register", next=request.url))
    if not user_has_role(["solucionador"]):
        return "Acesso negado.", 403

    item = itens_collection.find_one({"_id": ObjectId(item_id)})
    if not item:
        return "Item não encontrado.", 404

    file_obj = request.files.get("itemImage")
    if file_obj:
        image_ids = save_image(file_obj, fs_mz)
        if image_ids:
            new_main_id = image_ids["main_id"]
            new_thumb_id = image_ids["thumb_id"]
            old_main_id = item.get("itemImage_main")
            old_thumb_id = item.get("itemImage_thumb")
            if old_main_id:
                try:
                    fs_mz.delete(ObjectId(old_main_id))
                except:
                    pass
            if old_thumb_id:
                try:
                    fs_mz.delete(ObjectId(old_thumb_id))
                except:
                    pass

            itens_collection.update_one(
                {"_id": ObjectId(item_id)},
                {
                    "$set": {
                        "itemImage_main": new_main_id,
                        "itemImage_thumb": new_thumb_id
                    }
                }
            )

    return redirect(url_for("item_search"))

@app.route("/add_item", methods=["GET", "POST"])
def add_item():
    if not user_is_logged_in():
        return redirect(url_for("register", next=request.url))

    if request.method == "POST":
        description = request.form.get("description", "").strip()
        tags_str = request.form.get("tags", "").strip()
        user_tags_raw = tags_str.split() if tags_str else []
        user_tags_normalized = normalize_string(" ".join(user_tags_raw))
        final_user_tags = [t for t in user_tags_normalized.split() if t and t not in STOPWORDS]

        description_normalized = normalize_string(description)
        description_tokens = [t for t in description_normalized.split() if t and t not in STOPWORDS]
        all_tags = list(set(final_user_tags + description_tokens))

        price = request.form.get("price", "0").strip()
        try:
            price = float(price)
        except:
            price = 0.0
        stock_mz = request.form.get("stock_mz", "0").strip()
        try:
            stock_mz = int(stock_mz)
        except:
            stock_mz = 0
        stock_eld = request.form.get("stock_eld", "0").strip()
        try:
            stock_eld = int(stock_eld)
        except:
            stock_eld = 0

        image_file = request.files.get("itemImage")
        image_ids = save_image(image_file, fs_mz)

        if image_ids:
            main_id = image_ids["main_id"]
            thumb_id = image_ids["thumb_id"]
        else:
            main_id = None
            thumb_id = None

        new_item = {
            "description": description,
            "tags": all_tags,
            "price": price,
            "stock_mz": stock_mz,
            "stock_eld": stock_eld,
            "itemImage_main": main_id,
            "itemImage_thumb": thumb_id
        }
        itens_collection.insert_one(new_item)
        return redirect(url_for("item_search"))

    return render_template("add_item.html")

# -----------------------------------------------------------
# PERFIL + COMPARTILHAMENTO
# -----------------------------------------------------------
@app.route("/perfil", methods=["GET"])
def perfil():
    if not user_is_logged_in():
        return redirect(url_for("register", next=request.url))

    user_id = session["user_id"]
    user_obj = usuarios_collection.find_one({"_id": ObjectId(user_id)})
    if not user_obj:
        return "Usuário não encontrado.", 404

    random_bg = session.get("random_bg", "fundo1.jpeg")

    posted_count = problemas_collection.count_documents({"creator_id": user_id})
    solved_count = problemas_collection.count_documents({"solver_id": user_id, "resolvido": True})

    # Cálculo de nível
    level, level_name, points, remaining_for_next_level, progress_percentage, estimate_str = calculate_user_level(
        posted_count, solved_count
    )

    user_badges = []
    if posted_count >= 1:
        user_badges.append("Primeira Postagem")
    if solved_count >= 5:
        user_badges.append("Solucionador de Ouro")

    # Buscar últimos problemas criados
    latest_problems_cursor = problemas_collection.find({"creator_id": user_id}).sort("_id", -1).limit(3)
    latest_problems = list(latest_problems_cursor)
    for p in latest_problems:
        p["_id_str"] = str(p["_id"])

    # Buscar últimos problemas resolvidos
    latest_solved_cursor = problemas_collection.find({"solver_id": user_id, "resolvido": True}).sort("_id", -1).limit(3)
    latest_solved_problems = list(latest_solved_cursor)
    for p in latest_solved_problems:
        p["_id_str"] = str(p["_id"])

    return render_template(
        "profil.html",
        user=user_obj,
        posted_count=posted_count,
        solved_count=solved_count,
        level=level,
        level_name=level_name,
        points=points,
        remaining_for_next_level=remaining_for_next_level,
        progress_percentage=progress_percentage,
        estimate_str=estimate_str,
        user_badges=user_badges,
        latest_problems=latest_problems,          # CRIADOS
        latest_solved_problems=latest_solved_problems,  # RESOLVIDOS
        random_bg=random_bg
    )

@app.route("/edit_profile", methods=["GET", "POST"])
def edit_profile():
    if not user_is_logged_in():
        return redirect(url_for("register", next=request.url))

    user_id = session["user_id"]
    user_obj = usuarios_collection.find_one({"_id": ObjectId(user_id)})
    if not user_obj:
        return "Usuário não encontrado.", 404

    if request.method == "POST":
        novo_nome = request.form.get("nome", "").strip()
        if novo_nome:
            usuarios_collection.update_one(
                {"_id": ObjectId(user_id)},
                {"$set": {"nome": novo_nome}}
            )
            session["username"] = novo_nome

        profile_photo = request.files.get("profile_photo")
        if profile_photo and profile_photo.filename.strip():
            image_ids = save_image(profile_photo, fs_m)
            if image_ids:
                new_file_id = image_ids["main_id"]
                old_photo_id = user_obj.get("profile_image_id")
                if old_photo_id:
                    try:
                        fs_m.delete(ObjectId(old_photo_id))
                    except:
                        pass
                usuarios_collection.update_one(
                    {"_id": ObjectId(user_id)},
                    {"$set": {"profile_image_id": str(new_file_id)}}
                )

        return redirect(url_for("perfil"))

    return render_template("edit_profile.html", user=user_obj)

@app.route("/user_photo/<file_id>")
def get_user_photo(file_id):
    try:
        gridout = fs_m.get(ObjectId(file_id))
        image_data = gridout.read()
        content_type = gridout.contentType or "image/jpeg"
        response = make_response(image_data)
        response.headers.set('Content-Type', content_type)
        return response
    except:
        return "Foto não encontrada.", 404

@app.route("/get_profile_share_link", methods=["POST"])
def get_profile_share_link():
    """
    Gera (ou recupera) o token de perfil do usuário logado e retorna o link
    para a rota `perfil_usuario` (página pública do perfil).
    """
    if not user_is_logged_in():
        return jsonify({"error": "Não autorizado"}), 401

    user_id = session["user_id"]
    user_doc = usuarios_collection.find_one({"_id": ObjectId(user_id)})

    # Se não tem token, gera
    if not user_doc.get("perfil_token"):
        new_token = secrets.token_urlsafe(16)
        usuarios_collection.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"perfil_token": new_token}}
        )
        user_doc["perfil_token"] = new_token

    # O link público passa a ser -> /perfil_usuario/<token>
    share_url = url_for("perfil_usuario", token=user_doc["perfil_token"], _external=True)
    return jsonify({"share_url": share_url})

@app.route("/perfil_usuario/<token>")
def perfil_usuario(token):
    """
    Exibe o perfil público do usuário, usando o template 'perfil_usuario.html'.
    """
    user_doc = usuarios_collection.find_one({"perfil_token": token})
    if not user_doc:
        return "Perfil não encontrado ou token inválido.", 404

    user_id_str = str(user_doc["_id"])
    posted_count = problemas_collection.count_documents({"creator_id": user_id_str})
    solved_count = problemas_collection.count_documents({"solver_id": user_id_str, "resolvido": True})

    level, level_name, points, remaining_for_next_level, progress_percentage, estimate_str = calculate_user_level(
        posted_count, solved_count
    )

    user_badges = []
    if posted_count >= 1:
        user_badges.append("Primeira Postagem")
    if solved_count >= 5:
        user_badges.append("Solucionador de Ouro")

    # Últimos problemas criados
    latest_problems_cursor = problemas_collection.find({"creator_id": user_id_str}).sort("_id", -1).limit(3)
    latest_problems = list(latest_problems_cursor)
    for p in latest_problems:
        p["_id_str"] = str(p["_id"])

    # Agora, se quiser mostrar ou não os problemas resolvidos, você pode buscar
    # Exemplo: iremos buscar resolvidos por esse usuário
    solved_problems_cursor = problemas_collection.find(
        {"solver_id": user_id_str, "resolvido": True}
    ).sort("_id", -1).limit(3)
    solved_problems = list(solved_problems_cursor)
    for sp in solved_problems:
        sp["_id_str"] = str(sp["_id"])

    # Passamos tudo para o template perfil_usuario.html
    return render_template(
        "perfil_usuario.html",
        user=user_doc,
        posted_count=posted_count,
        solved_count=solved_count,
        level=level,
        level_name=level_name,
        points=points,
        remaining_for_next_level=remaining_for_next_level,
        progress_percentage=progress_percentage,
        estimate_str=estimate_str,
        user_badges=user_badges,
        latest_problems=latest_problems,
        solved_problems=solved_problems
    )

# -----------------------------------------------------------
# FEEDBACK "SIM/NAO" (LIKE/DISLIKE)
# -----------------------------------------------------------
@app.route("/toggle_helpful", methods=["POST"])
def toggle_helpful():
    if not user_is_logged_in():
        return jsonify({"error": "Login necessário"}), 401

    data = request.get_json()
    problem_id = data.get("problem_id")
    desired_feedback = data.get("feedback")

    if not problem_id or not desired_feedback:
        return jsonify({"error": "Dados incompletos."}), 400

    existing_doc = helpful_feedback_collection.find_one({
        "problem_id": problem_id,
        "user_id": session["user_id"]
    })

    if not existing_doc:
        new_doc = {
            "problem_id": problem_id,
            "user_id": session["user_id"],
            "feedback": desired_feedback,
            "timestamp": datetime.datetime.utcnow()
        }
        helpful_feedback_collection.insert_one(new_doc)
        like_count = helpful_feedback_collection.count_documents({
            "problem_id": problem_id,
            "feedback": "SIM"
        })
        return jsonify({"status": "created", "feedback": desired_feedback, "like_count": like_count})
    else:
        current_feedback = existing_doc["feedback"]
        if current_feedback == desired_feedback:
            helpful_feedback_collection.delete_one({"_id": existing_doc["_id"]})
            like_count = helpful_feedback_collection.count_documents({
                "problem_id": problem_id,
                "feedback": "SIM"
            })
            return jsonify({"status": "removed", "feedback": None, "like_count": like_count})
        else:
            helpful_feedback_collection.update_one(
                {"_id": existing_doc["_id"]},
                {"$set": {"feedback": desired_feedback, "timestamp": datetime.datetime.utcnow()}}
            )
            like_count = helpful_feedback_collection.count_documents({
                "problem_id": problem_id,
                "feedback": "SIM"
            })
            return jsonify({"status": "updated", "feedback": desired_feedback, "like_count": like_count})

# -----------------------------------------------------------
# FEEDBACK DE PASSO ESPECÍFICO
# -----------------------------------------------------------
@app.route("/submit_step_feedback", methods=["POST"])
def submit_step_feedback():
    if not user_is_logged_in():
        return jsonify({"error": "Login necessário"}), 401

    data = request.get_json()
    problem_id = data.get("problem_id")
    step_index = data.get("step_index")
    success = data.get("success")
    feedback_text = data.get("feedback_text", "").strip()

    if problem_id is None or step_index is None or success is None:
        return jsonify({"error": "Dados incompletos"}), 400

    step_feedback_collection.insert_one({
        "problem_id": problem_id,
        "user_id": session["user_id"],
        "step_index": step_index,
        "success": success,
        "feedback_text": feedback_text,
        "timestamp": datetime.datetime.utcnow()
    })
    return jsonify({"message": "Feedback registrado com sucesso!"})

# -----------------------------------------------------------
# ROTA PARA EXIBIR PERFIL DE OUTRO USUÁRIO (INTERNAMENTE)
# -----------------------------------------------------------
@app.route("/ver_usuario/<user_id>", methods=["GET"])
def ver_usuario(user_id):
    """
    Exibe o perfil de um outro usuário qualquer (não o logado),
    usando o template 'perfil_usuario.html' ou similar.
    """
    user_doc = usuarios_collection.find_one({"_id": ObjectId(user_id)})
    if not user_doc:
        return "Usuário não encontrado.", 404

    posted_count = problemas_collection.count_documents({"creator_id": user_id})
    solved_count = problemas_collection.count_documents({"solver_id": user_id, "resolvido": True})

    level, level_name, points, remaining_for_next_level, progress_percentage, estimate_str = calculate_user_level(
        posted_count, solved_count
    )

    user_badges = []
    if posted_count >= 1:
        user_badges.append("Primeira Postagem")
    if solved_count >= 5:
        user_badges.append("Solucionador de Ouro")

    latest_problems_cursor = problemas_collection.find({"creator_id": user_id}).sort("_id", -1).limit(3)
    latest_problems = list(latest_problems_cursor)
    for p in latest_problems:
        p["_id_str"] = str(p["_id"])

    # Se quiser buscar problemas que este user resolveu:
    solved_problems_cursor = problemas_collection.find(
        {"solver_id": user_id, "resolvido": True}
    ).sort("_id", -1).limit(3)
    solved_problems = list(solved_problems_cursor)
    for sp in solved_problems:
        sp["_id_str"] = str(sp["_id"])

    # Reutilizamos o template "perfil_usuario.html"
    # Mas note que esse template está formatado para uso público (token).
    # Internamente podemos usar a mesma ideia, só que sem token.
    return render_template(
        "perfil_usuario.html",
        user=user_doc,
        posted_count=posted_count,
        solved_count=solved_count,
        level=level,
        level_name=level_name,
        points=points,
        remaining_for_next_level=remaining_for_next_level,
        progress_percentage=progress_percentage,
        estimate_str=estimate_str,
        user_badges=user_badges,
        latest_problems=latest_problems,
        solved_problems=solved_problems
    )

# -----------------------------------------------------------
# MAIN
# -----------------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
