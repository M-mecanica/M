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
from werkzeug.security import generate_password_hash, check_password_hash
import gridfs

# Biblioteca para criar thumbnails
from PIL import Image
import io

app = Flask(__name__)

# -----------------------------------------------------------
# CONFIGURAÇÃO BÁSICA
# -----------------------------------------------------------
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "CHAVE_SECRETA_PARA_SESSAO_INSEGURA")

# -----------------------------------------------------------
# CONEXÃO COM O MONGO - BANCO M (Plataforma)
# -----------------------------------------------------------
client_m = MongoClient(
    "mongodb+srv://msolucoesmecanicasinteligentes:solucao@cluster0.7ljuh.mongodb.net/"
)
db_m = client_m["m_plataforma"]

# Coleções do M
problemas_collection = db_m["problemas"]
usuarios_collection = db_m["usuarios"]
history_collection = db_m["search_history"]  # Histórico de buscas de PEÇAS
problem_history_collection = db_m["problem_search_history"]  # Histórico de busca de PROBLEMAS
problem_view_history_collection = db_m["problem_view_history"]  # Registro de visualizações
improvement_suggestions_collection = db_m["improvement_suggestions"]  # Sugestões de melhorias

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

ITEMS_PER_PAGE = 20  # Usado tanto para itens quanto para problemas
MZ_WHATSAPP = "5543996436367"  # Número WhatsApp para finalizar carrinho, etc.

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
    Remove acentos e deixa tudo em minúsculo, sem espaços extras.
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
    Ex.: ["rolamento", "grande", "da", "redução"] -> sub-frases.
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

def create_thumbnail(image_bytes, max_size=(300, 300)):
    """
    Cria um thumbnail a partir dos bytes de imagem (bytes do arquivo original).
    Retorna os bytes do thumbnail em formato JPEG.
    """
    img = Image.open(io.BytesIO(image_bytes))
    img.thumbnail(max_size)  # Reduz a imagem mantendo a proporção
    output = io.BytesIO()
    # Salva em JPEG (poderia ser PNG, WEBP etc.)
    img.save(output, format="JPEG", quality=85)
    output.seek(0)
    return output.read()

def save_image_with_thumbnail(file_obj, fs_instance):
    """
    Salva a imagem original e o thumbnail no GridFS (fs_instance).
    Retorna (original_id, thumb_id).
    Se não houver arquivo ou estiver vazio, retorna (None, None).
    """
    if not file_obj or file_obj.filename.strip() == "":
        return None, None

    file_data = file_obj.read()
    if not file_data:
        return None, None

    content_type = file_obj.content_type
    filename = secure_filename(file_obj.filename)

    # Armazena imagem original
    original_id = fs_instance.put(
        file_data,
        filename=filename,
        contentType=content_type
    )

    # Gera e armazena thumbnail
    thumb_data = create_thumbnail(file_data)
    thumb_filename = "thumb_" + filename
    thumb_id = fs_instance.put(
        thumb_data,
        filename=thumb_filename,
        contentType="image/jpeg"
    )

    return str(original_id), str(thumb_id)

# -----------------------------------------------------------
# ROTA PRINCIPAL E SISTEMA DE USUÁRIOS
# -----------------------------------------------------------
@app.route("/")
def root():
    return redirect(url_for("index"))

@app.route("/index", methods=["GET"])
def index():
    need_login = request.args.get("need_login", "0")
    return render_template("index.html", need_login=need_login)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        senha = request.form.get("senha", "").strip()
        # Capitaliza cada palavra do nome
        nome = " ".join(word.capitalize() for word in nome.split())

        usuario = usuarios_collection.find_one({"nome": nome})
        if usuario:
            stored_hash = usuario.get("senha_hash")
            if stored_hash:
                # Verifica senha baseada em hash
                if check_password_hash(stored_hash, senha):
                    session["user_id"] = str(usuario["_id"])
                    session["username"] = usuario["nome"]
                    session["role"] = usuario["role"]
                    return redirect(url_for("index"))
                else:
                    return render_template("login.html", erro="Usuário ou senha inválidos.")
            else:
                # Fallback para usuários antigos (sem hash)
                if usuario.get("senha") == senha:
                    # Migra para hash
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
    return redirect(url_for("login"))

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        senha = request.form.get("senha", "").strip()
        confirmar_senha = request.form.get("confirmar_senha", "").strip()
        whatsapp = request.form.get("whatsapp", "").strip()
        maquinas = request.form.get("maquinas", "").strip()

        if senha != confirmar_senha:
            return render_template("register.html", erro="As senhas não conferem!")

        nome = " ".join(word.capitalize() for word in nome.split())

        # Verifica duplicado
        if usuarios_collection.find_one({"nome": nome}):
            return render_template("register.html", erro="Usuário já existe!")

        senha_hash = generate_password_hash(senha)
        novo_usuario = {
            "nome": nome,
            "senha_hash": senha_hash,
            "role": "comum",
            "whatsapp": whatsapp,
            "maquinas": maquinas
        }
        inserted = usuarios_collection.insert_one(novo_usuario)
        new_user_id = str(inserted.inserted_id)

        session["user_id"] = new_user_id
        session["username"] = nome
        session["role"] = "comum"

        return redirect(url_for("index"))

    return render_template("register.html", erro=None)

# -----------------------------------------------------------
# ROTAS LIGADAS A PROBLEMAS (Plataforma M)
# -----------------------------------------------------------

@app.route("/search", methods=["GET"])
def search():
    termo_busca = request.args.get("q", "").strip()
    return render_template("resultados.html", termo_busca=termo_busca)

@app.route("/load_problems", methods=["GET"])
def load_problems():
    """
    Fornece problemas em formato JSON para a página resultados.html fazer scroll infinito.
    Se 'q' (search_query) estiver vazio, retorna problemas aleatórios.
    Se houver busca, faz a busca com skip/limit.
    """
    search_query = request.args.get("q", "").strip()
    page = int(request.args.get("page", 1))

    # Para logar a pesquisa em 'problem_history_collection'
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

    if search_query:
        # PESQUISA COM SKIP/LIMIT
        skip = (page - 1) * ITEMS_PER_PAGE

        normalized_search_phrase = normalize_string(search_query)
        search_tokens = [t for t in normalized_search_phrase.split() if t and t not in STOPWORDS]

        pipeline_base = [
            {
                "$match": {
                    "$or": [
                        {"titulo": {"$regex": search_query, "$options": "i"}},
                        {"descricao": {"$regex": search_query, "$options": "i"}},
                        {"tags": {"$all": search_tokens}}  # AND de tokens
                    ]
                }
            }
        ]

        # Contar total
        count_pipeline = pipeline_base + [{"$count": "total"}]
        count_result = list(problemas_collection.aggregate(count_pipeline))
        total_count = count_result[0]["total"] if count_result else 0

        # Carregar problemas
        pipeline_fetch = pipeline_base + [
            {"$skip": skip},
            {"$limit": ITEMS_PER_PAGE}
        ]
        problems_cursor = problemas_collection.aggregate(pipeline_fetch)
        problems = list(problems_cursor)

        problems_list = []
        for p in problems:
            problems_list.append({
                "_id": str(p["_id"]),
                "titulo": p.get("titulo", ""),
                "descricao": p.get("descricao", ""),
                "resolvido": p.get("resolvido", False),
                # Se tivermos thumbnail, enviamos no JSON
                "problemImage": str(p["problemImage"]) if p.get("problemImage") else None,
                "problemImageThumb": str(p["problemImageThumb"]) if p.get("problemImageThumb") else None
            })

        has_more = (skip + ITEMS_PER_PAGE) < total_count
        return jsonify({
            "problems": problems_list,
            "has_more": has_more,
            "total_count": total_count
        })

    else:
        # LÓGICA DE ALEATORIEDADE SE NÃO HOUVER BUSCA
        if page == 1:
            session["displayed_problem_ids"] = []
        displayed_ids = session.get("displayed_problem_ids", [])

        displayed_object_ids = [ObjectId(x) for x in displayed_ids]

        pipeline_count = [
            {"$match": {"_id": {"$nin": displayed_object_ids}}},
            {"$count": "remaining_count"}
        ]
        count_res = list(problemas_collection.aggregate(pipeline_count))
        remaining_count = count_res[0]["remaining_count"] if count_res else 0

        if remaining_count <= 0:
            return jsonify({
                "problems": [],
                "has_more": False,
                "total_count": 0
            })
        else:
            fetch_size = min(ITEMS_PER_PAGE, remaining_count)
            pipeline_sample = [
                {"$match": {"_id": {"$nin": displayed_object_ids}}},
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
                problems_list.append({
                    "_id": str(p["_id"]),
                    "titulo": p.get("titulo", ""),
                    "descricao": p.get("descricao", ""),
                    "resolvido": p.get("resolvido", False),
                    "problemImage": str(p["problemImage"]) if p.get("problemImage") else None,
                    "problemImageThumb": str(p["problemImageThumb"]) if p.get("problemImageThumb") else None
                })

            return jsonify({
                "problems": problems_list,
                "has_more": has_more,
                "total_count": remaining_count
            })

@app.route("/add", methods=["GET", "POST"])
def add_problem():
    if not user_is_logged_in():
        return redirect(url_for("index", need_login=1))

    if request.method == "POST":
        titulo = request.form.get("titulo", "").strip()
        descricao = request.form.get("descricao", "").strip()
        titulo_normalized = normalize_string(titulo)
        titulo_tokens = [t for t in titulo_normalized.split() if t not in STOPWORDS]

        tags_str = request.form.get("tags", "").strip()
        user_tags_raw = tags_str.split()
        user_tags_normalized = [normalize_string(t) for t in user_tags_raw if t.strip()]
        user_tags_normalized = [t for t in user_tags_normalized if t not in STOPWORDS]

        all_tags = list(set(titulo_tokens + user_tags_normalized))

        # Lida com a imagem + thumbnail
        image_file = request.files.get("problemImage")
        original_id, thumb_id = save_image_with_thumbnail(image_file, fs_m)

        if titulo and descricao:
            problema = {
                "titulo": titulo,
                "descricao": descricao,
                "resolvido": False,
                "tags": all_tags,
                "creator_id": session["user_id"],
                "problemImage": original_id,
                "problemImageThumb": thumb_id
            }
            problemas_collection.insert_one(problema)
            return redirect(url_for("unresolved"))
        else:
            return render_template("add.html", erro="Preencha todos os campos.")
    return render_template("add.html", erro=None)

@app.route("/unresolved", methods=["GET"])
def unresolved():
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
    if not user_is_logged_in():
        return redirect(url_for("index", need_login=1))
    if not user_has_role(["solucionador", "mecanico"]):
        return "Acesso negado (somente solucionadores/mecânicos).", 403
    return render_template("resolver.html", problem_id=problem_id)

@app.route("/resolver/<problem_id>", methods=["POST"])
def resolver_problema(problem_id):
    if not user_is_logged_in():
        return redirect(url_for("index", need_login=1))
    if not user_has_role(["solucionador", "mecanico"]):
        return "Acesso negado (somente solucionadores/mecânicos).", 403

    solution_json = request.form.get("solution_data", "")
    try:
        solution_data = json.loads(solution_json)
    except json.JSONDecodeError:
        solution_data = {}

    problemas_collection.update_one(
        {"_id": ObjectId(problem_id)},
        {"$set": {"resolvido": True, "solucao": solution_data}}
    )
    return redirect(url_for("unresolved"))

@app.route("/solucao/<problem_id>", methods=["GET"])
def exibir_solucao(problem_id):
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
    if not user_is_logged_in():
        return redirect(url_for("index", need_login=1))
    if not user_has_role(["solucionador"]):
        return "Acesso negado (somente solucionador).", 403

    problema = problemas_collection.find_one({"_id": ObjectId(problem_id)})
    if not problema:
        return "Problema não encontrado.", 404

    # Se houver imagem e thumbnail no problema, podemos excluí-los do GridFS:
    old_file_id = problema.get("problemImage")
    if old_file_id:
        try:
            fs_m.delete(ObjectId(old_file_id))
        except:
            pass

    old_thumb_id = problema.get("problemImageThumb")
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
        return redirect(url_for("index", need_login=1))

    problema = problemas_collection.find_one({"_id": ObjectId(problem_id)})
    if not problema:
        return "Problema não encontrado.", 404

    can_edit = (session["user_id"] == problema["creator_id"]) or user_has_role(["solucionador"])
    if not can_edit:
        return "Acesso negado.", 403

    if request.method == "POST":
        titulo_novo = request.form.get("titulo", "").strip()
        descricao_nova = request.form.get("descricao", "").strip()

        titulo_normalized = normalize_string(titulo_novo)
        titulo_tokens = [t for t in titulo_normalized.split() if t not in STOPWORDS]

        tags_str = request.form.get("tags", "").strip()
        user_tags_raw = tags_str.split()
        user_tags_normalized = [normalize_string(t) for t in user_tags_raw if t.strip()]
        user_tags_normalized = [t for t in user_tags_normalized if t not in STOPWORDS]

        all_tags = list(set(titulo_tokens + user_tags_normalized))

        if not titulo_novo or not descricao_nova:
            return render_template("edit_problem.html", problema=problema, erro="Preencha todos os campos.")

        updated_fields = {
            "titulo": titulo_novo,
            "descricao": descricao_nova,
            "tags": all_tags
        }

        # Lida com a imagem do problema + thumbnail
        delete_image = request.form.get("deleteExistingImage", "false") == "true"
        image_file = request.files.get("problemImage")

        # Se o usuário quer apagar a imagem
        if delete_image:
            old_file_id = problema.get("problemImage")
            old_thumb_id = problema.get("problemImageThumb")
            if old_file_id:
                try:
                    fs_m.delete(ObjectId(old_file_id))
                except:
                    pass
            if old_thumb_id:
                try:
                    fs_m.delete(ObjectId(old_thumb_id))
                except:
                    pass
            updated_fields["problemImage"] = None
            updated_fields["problemImageThumb"] = None

        # Se subiu imagem nova, cria e substitui
        elif image_file and image_file.filename.strip():
            new_orig_id, new_thumb_id = save_image_with_thumbnail(image_file, fs_m)

            # Exclui a antiga, se houver
            old_file_id = problema.get("problemImage")
            if old_file_id:
                try:
                    fs_m.delete(ObjectId(old_file_id))
                except:
                    pass

            old_thumb_id = problema.get("problemImageThumb")
            if old_thumb_id:
                try:
                    fs_m.delete(ObjectId(old_thumb_id))
                except:
                    pass

            updated_fields["problemImage"] = new_orig_id
            updated_fields["problemImageThumb"] = new_thumb_id

        problemas_collection.update_one(
            {"_id": ObjectId(problem_id)},
            {"$set": updated_fields}
        )
        return redirect(url_for("search", q=titulo_novo))

    return render_template("edit_problem.html", problema=problema, erro=None)

@app.route("/edit_user_role/<user_id>", methods=["POST"])
def edit_user_role(user_id):
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
    if not user_is_logged_in():
        return redirect(url_for("index", need_login=1))
    if not user_has_role(["solucionador"]):
        return "Acesso negado.", 403

    usuarios_collection.delete_one({"_id": ObjectId(user_id)})
    return redirect(url_for("listar_usuarios"))

@app.route("/edit_solution/<problem_id>", methods=["GET", "POST"])
def edit_solution(problem_id):
    if not user_is_logged_in():
        return redirect(url_for("index", need_login=1))
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
            # Lidar com imagem do step
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
                # salva nova
                orig_id, thumb_id = save_image_with_thumbnail(step_image_file, fs_m)
                # Exclui antiga
                if old_file_id:
                    try:
                        fs_m.delete(ObjectId(old_file_id))
                    except:
                        pass
                step["stepImage"] = orig_id
                # Se quiser, poderíamos também salvar "stepImageThumb", se aplicável
            else:
                # Mantém a anterior
                step["stepImage"] = old_file_id

            # Subpassos
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
                    # salva nova
                    orig_sub_id, thumb_sub_id = save_image_with_thumbnail(substep_file, fs_m)
                    if old_sub_file_id:
                        try:
                            fs_m.delete(ObjectId(old_sub_file_id))
                        except:
                            pass
                    substep["subStepImage"] = orig_sub_id
                else:
                    # Mantém a anterior
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

# -----------------------------------------------------------
# GRIDFS - EXIBIÇÃO DE IMAGENS (PROBLEMAS)
# -----------------------------------------------------------
@app.route("/gridfs_image/<file_id>", methods=["GET"])
def gridfs_image(file_id):
    """
    Exibe a versão ORIGINAL da imagem
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

@app.route("/gridfs_image_thumb/<file_id>", methods=["GET"])
def gridfs_image_thumb(file_id):
    """
    Exibe a versão THUMBNAIL da imagem
    """
    try:
        gridout = fs_m.get(ObjectId(file_id))
        image_data = gridout.read()
        # Forçamos tipo "image/jpeg" já que salvamos como JPEG
        response = make_response(image_data)
        response.headers.set('Content-Type', "image/jpeg")
        return response
    except:
        return "Thumbnail não encontrada.", 404

# -----------------------------------------------------------
# GRIDFS - EXIBIÇÃO DE IMAGENS (ITENS)
# -----------------------------------------------------------
@app.route("/gridfs_item_image/<file_id>", methods=["GET"])
def gridfs_item_image(file_id):
    """
    Exibe a imagem do item armazenada em fs_mz pelo ID do arquivo (VERSÃO ORIGINAL).
    """
    try:
        gridout = fs_mz.get(ObjectId(file_id))
        image_data = gridout.read()
        content_type = gridout.contentType or "image/jpeg"
        response = make_response(image_data)
        response.headers.set('Content-Type', content_type)
        return response
    except:
        return "Imagem do item não encontrada.", 404

# Você pode criar rotas similares para thumbnails de itens, se desejar:
# @app.route("/gridfs_item_image_thumb/<file_id>", methods=["GET"])
# def gridfs_item_image_thumb(file_id):
#     pass

# -----------------------------------------------------------
# HISTÓRICOS
# -----------------------------------------------------------
@app.route("/history_search", methods=["GET"])
def history_search():
    if not user_is_logged_in():
        return redirect(url_for("index", need_login=1))
    if not user_has_role(["solucionador"]):
        return "Acesso negado.", 403

    all_history = list(history_collection.find({}))
    return render_template("history_search.html", history=all_history)

@app.route("/history_problem", methods=["GET"])
def history_problem():
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

# -----------------------------------------------------------
# PESQUISA DE ITENS (MZ) + Upload de imagem
# -----------------------------------------------------------
@app.route("/item_search", methods=["GET"])
def item_search():
    return render_template("item_search.html")

@app.route("/load_items", methods=["GET"])
def load_items():
    """
    Retorna JSON com até ITEMS_PER_PAGE itens por página.
      - Se 'search' não está vazio, faz a busca com relevância.
      - Se 'search' está vazio, seleciona aleatoriamente itens
        ainda não exibidos na sessão.
    """
    search_query = request.args.get('search', '').strip()
    page = int(request.args.get('page', 1))

    if search_query:
        # Log de pesquisa
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

        # Carregar matching (não paginado ainda, para depois fazermos slice)
        items_cursor = itens_collection.aggregate(
            pipeline_base,
            collation={'locale': 'pt', 'strength': 1}
        )
        items = list(items_cursor)

        # Calcular maior sub-frase
        for item in items:
            item['largest_sub_phrase_length'] = compute_largest_sub_phrase_length(
                search_tokens,
                item.get('matching_phrases', [])
            )

        # Ordena: 1) is_phrase_match desc, 2) largest_sub_phrase_length desc, 3) description asc
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
                'itemImage': str(it['itemImage']) if it.get('itemImage') else None
                # Você pode adicionar itemImageThumb se também gerar thumbnails de itens
            })

        return jsonify({
            'items': items_list,
            'has_more': has_more,
            'total_items': total_items
        })

    else:
        # Caso SEM TERMO: PAGINAÇÃO ALEATÓRIA
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
                'itemImage': str(it['itemImage']) if it.get('itemImage') else None
            })

        return jsonify({
            "items": response_items,
            "has_more": has_more,
            "total_items": remaining_count
        })

@app.route("/upload_item_image/<item_id>", methods=["POST"])
def upload_item_image(item_id):
    """
    Permite que um usuário com papel 'solucionador' envie (ou substitua) a imagem de um item.
    (Você poderia criar e salvar thumbnail da mesma forma que em problemas.)
    """
    if not user_is_logged_in():
        return "Acesso negado. Faça login.", 403
    if not user_has_role(["solucionador"]):
        return "Acesso negado. Apenas solucionadores podem enviar imagens de itens.", 403

    item = itens_collection.find_one({"_id": ObjectId(item_id)})
    if not item:
        return "Item não encontrado.", 404

    file_obj = request.files.get("itemImage")
    if file_obj:
        file_data = file_obj.read()
        if file_data:
            content_type = file_obj.content_type
            filename = secure_filename(file_obj.filename)

            # Armazena original (poderia também criar thumbnail)
            new_file_id = fs_mz.put(
                file_data,
                filename=filename,
                contentType=content_type
            )

            old_file_id = item.get("itemImage")
            if old_file_id:
                try:
                    fs_mz.delete(ObjectId(old_file_id))
                except:
                    pass

            itens_collection.update_one(
                {"_id": ObjectId(item_id)},
                {"$set": {"itemImage": str(new_file_id)}}
            )

    return redirect(url_for("item_search"))

# -----------------------------------------------------------
# EXECUÇÃO
# -----------------------------------------------------------
if __name__ == "__main__":
    # Em produção, lembre de usar debug=False
    app.run(host="0.0.0.0", port=5000, debug=True)
