import os
import json
import re
import unicodedata
from datetime import datetime

from flask import (
    Flask, render_template, request, redirect,
    url_for, session, jsonify, make_response
)
from pymongo import MongoClient
from bson.objectid import ObjectId
from werkzeug.utils import secure_filename
import gridfs

##############################################################################
#                           CONFIGURAÇÕES FLASK
##############################################################################

app = Flask(__name__)
app.secret_key = "CHAVE_SECRETA_PARA_SESSAO"  # Troque por algo seguro em produção

##############################################################################
#                CONEXÕES COM DOIS BANCOS DE DADOS MONGODB
##############################################################################

# ------------------------ DB do M (m_plataforma) ----------------------------
client_m = MongoClient(
    "mongodb+srv://msolucoesmecanicasinteligentes:solucao@cluster0.7ljuh.mongodb.net/"
)
db_m = client_m["m_plataforma"]

# Coleções do M
problemas_collection = db_m["problemas"]
usuarios_collection = db_m["usuarios"]

# GridFS para armazenar as imagens no DB "m_plataforma"
fs_m = gridfs.GridFS(db_m)

# Coleção para histórico de buscas de PEÇAS (já existente)
history_collection = db_m["search_history"]

# --- NOVA COLEÇÃO para histórico de pesquisa de PROBLEMAS ---
problem_history_collection = db_m["problem_search_history"]

# ------------------------ DB do MZ (MachineZONE) ----------------------------
client_mz = MongoClient(
    "mongodb+srv://adaltonmuzilomendes:rolamento@cluster0.atmeh.mongodb.net/"
)
db_mz = client_mz["MachineZONE"]

# Coleção principal de itens no MZ
itens_collection = db_mz["itens"]

##############################################################################
#                    FUNÇÕES AUXILIARES (UPLOAD, LOGIN ETC.)
##############################################################################

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

##############################################################################
#           FUNÇÕES DE NORMALIZAÇÃO E AVALIAÇÃO (PARA BUSCA MZ)
##############################################################################

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

##############################################################################
#              ROTAS DE LOGIN/LOGOUT/REGISTER (BANCO M)
##############################################################################

@app.route("/")
def root():
    """
    Se o usuário estiver logado, vai para /index, senão para /login.
    """
    if user_is_logged_in():
        return redirect(url_for("index"))
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    """
    Formulário de login no sistema (banco 'm_plataforma', coleção 'usuarios').
    """
    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        senha = request.form.get("senha", "").strip()

        usuario = usuarios_collection.find_one({"nome": nome, "senha": senha})
        if usuario:
            session["user_id"] = str(usuario["_id"])
            session["nome"] = usuario["nome"]
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
    """
    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        senha = request.form.get("senha", "").strip()
        role = "comum"
        whatsapp = request.form.get("whatsapp", "").strip()
        maquinas = request.form.get("maquinas", "").strip()

        # Verifica se usuário já existe
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
        usuarios_collection.insert_one(novo_usuario)
        return redirect(url_for("login"))

    return render_template("register.html", erro=None)

##############################################################################
#                ROTAS DO M (m_plataforma) - PROBLEMAS
##############################################################################

@app.route("/index", methods=["GET"])
def index():
    """
    Página inicial do sistema M (se logado, senão /login).
    """
    if not user_is_logged_in():
        return redirect(url_for("login"))
    return render_template("index.html")

@app.route("/search", methods=["GET"])
def search():
    """
    Pesquisa problemas resolvidos com base em 'q'.
    - Busca no 'titulo' (por regex case-insensitive) E/OU
    - Busca nas 'tags' (já normalizadas) por tokens (AND).
    Se 'q' estiver vazio, mostra todos os problemas resolvidos.

    Também registra histórico de pesquisa de PROBLEMAS em 'problem_history_collection'.
    """
    if not user_is_logged_in():
        return redirect(url_for("login"))

    termo_busca = request.args.get("q", "").strip()

    if termo_busca:
        # Normaliza o termo de busca para comparar com as tags normalizadas
        termo_busca_normalized = normalize_string(termo_busca)
        tokens = [t for t in termo_busca_normalized.split() if t]

        query = {
            "resolvido": True,
            "$or": [
                {"titulo": {"$regex": termo_busca, "$options": "i"}},
                {"tags": {"$all": tokens}}
            ]
        }

        # REGISTRAR no histórico de pesquisa de problemas
        problem_history_collection.insert_one({
            "user_id": session["user_id"],
            "user_name": session["nome"],
            "query": termo_busca,
            "timestamp": datetime.now()
        })

    else:
        query = {"resolvido": True}

    problemas_encontrados = list(problemas_collection.find(query))
    for p in problemas_encontrados:
        p["_id_str"] = str(p["_id"])

    return render_template(
        "resultados.html",
        problemas=problemas_encontrados,
        termo_busca=termo_busca
    )

@app.route("/add", methods=["GET", "POST"])
def add_problem():
    """
    Cadastra novo problema (não resolvido), com possibilidade de adicionar tags
    separadas por espaço. O título também entra como tags normalizadas.
    """
    if not user_is_logged_in():
        return redirect(url_for("login"))

    if request.method == "POST":
        titulo = request.form.get("titulo", "").strip()
        descricao = request.form.get("descricao", "").strip()

        # Normaliza e quebra o título para virar parte das tags
        titulo_normalized = normalize_string(titulo)
        titulo_tokens = titulo_normalized.split()

        # Normaliza também as tags fornecidas
        tags_str = request.form.get("tags", "").strip()
        user_tags_raw = tags_str.split()
        user_tags_normalized = [normalize_string(t) for t in user_tags_raw if t.strip()]

        # Unifica tudo em uma única lista, removendo duplicados
        all_tags = list(set(titulo_tokens + user_tags_normalized))

        if titulo and descricao:
            problema = {
                "titulo": titulo,
                "descricao": descricao,
                "resolvido": False,
                "tags": all_tags
            }
            problemas_collection.insert_one(problema)
            return redirect(url_for("unresolved"))
        else:
            return render_template("add.html", erro="Preencha todos os campos.")
    return render_template("add.html", erro=None)

@app.route("/unresolved", methods=["GET"])
def unresolved():
    """
    Lista problemas que ainda não foram resolvidos.
    """
    if not user_is_logged_in():
        return redirect(url_for("login"))

    query = {"resolvido": False}
    problemas_nao_resolvidos = list(problemas_collection.find(query))
    for p in problemas_nao_resolvidos:
        p["_id_str"] = str(p["_id"])

    return render_template("nao_resolvidos.html", problemas=problemas_nao_resolvidos)

@app.route("/resolver_form/<problem_id>", methods=["GET"])
def resolver_form(problem_id):
    """
    Exibe formulário para resolver um problema (roles 'solucionador' ou 'mecanico').
    """
    if not user_is_logged_in():
        return redirect(url_for("login"))
    if not user_has_role(["solucionador", "mecanico"]):
        return "Acesso negado (somente solucionadores/mecanicos).", 403

    return render_template("resolver.html", problem_id=problem_id)

@app.route("/resolver/<problem_id>", methods=["POST"])
def resolver_problema(problem_id):
    """
    Marca o problema como resolvido, salvando estrutura JSON de passos/subpassos.
    """
    if not user_is_logged_in():
        return redirect(url_for("login"))
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
    Exibe a página 'solucao.html' com a solução (se resolvido).
    """
    if not user_is_logged_in():
        return redirect(url_for("login"))

    problema = problemas_collection.find_one({"_id": ObjectId(problem_id)})
    if not problema:
        return "Problema não encontrado.", 404
    if not problema.get("resolvido"):
        return "Este problema ainda não foi marcado como resolvido.", 400

    solucao = problema.get("solucao", {})
    return render_template("solucao.html", problema=problema, solucao=solucao)

@app.route("/delete/<problem_id>", methods=["POST"])
def delete_problem(problem_id):
    """
    Deleta um problema (somente 'solucionador').
    """
    if not user_is_logged_in():
        return redirect(url_for("login"))
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
    Exibe um formulário (GET) para editar título/descrição/tags de um problema,
    e salva as alterações no banco (POST). Somente 'solucionador'.
    """
    if not user_is_logged_in():
        return redirect(url_for("login"))
    if not user_has_role(["solucionador"]):
        return "Acesso negado.", 403

    problema = problemas_collection.find_one({"_id": ObjectId(problem_id)})
    if not problema:
        return "Problema não encontrado.", 404

    if request.method == "POST":
        titulo_novo = request.form.get("titulo", "").strip()
        descricao_nova = request.form.get("descricao", "").strip()

        # Normaliza e quebra o título para virar parte das tags
        titulo_normalized = normalize_string(titulo_novo)
        titulo_tokens = titulo_normalized.split()

        # Normaliza também as tags informadas
        tags_str = request.form.get("tags", "").strip()
        user_tags_raw = tags_str.split()
        user_tags_normalized = [normalize_string(t) for t in user_tags_raw if t.strip()]

        all_tags = list(set(titulo_tokens + user_tags_normalized))

        if not titulo_novo or not descricao_nova:
            erro = "Preencha todos os campos de título e descrição."
            return render_template("edit_problem.html", problema=problema, erro=erro)

        # Atualiza no banco
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

##############################################################################
#            ROTA PARA EDITAR FUNÇÃO DO USUÁRIO (SOLUCIONADOR)
##############################################################################

@app.route("/edit_user_role/<user_id>", methods=["POST"])
def edit_user_role(user_id):
    """
    Permite que um 'solucionador' altere a função (role) de um usuário.
    """
    if not user_is_logged_in():
        return redirect(url_for("login"))
    if not user_has_role(["solucionador"]):
        return "Acesso negado.", 403

    novo_role = request.form.get("role", "comum").strip()
    usuarios_collection.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"role": novo_role}}
    )
    return redirect(url_for("listar_usuarios"))

##############################################################################
#                ROTAS PARA LISTAR/DELETAR USUÁRIOS
##############################################################################

@app.route("/usuarios", methods=["GET"])
def listar_usuarios():
    """
    Lista todos os usuários (somente 'solucionador').
    Agora com sistema de pesquisa por nome, whatsapp ou máquinas.
    E agora também com botão para HISTÓRICO de pesquisa de problemas.
    """
    if not user_is_logged_in():
        return redirect(url_for("login"))
    if not user_has_role(["solucionador"]):
        return "Acesso negado.", 403

    # Captura o termo de pesquisa
    search_query = request.args.get("q", "").strip()

    # Monta o filtro para MongoDB
    if search_query:
        query = {
            "$or": [
                {"nome": {"$regex": search_query, "$options": "i"}},
                {"whatsapp": {"$regex": search_query, "$options": "i"}},
                {"maquinas": {"$regex": search_query, "$options": "i"}},
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
    Deleta um usuário (somente 'solucionador').
    """
    if not user_is_logged_in():
        return redirect(url_for("login"))
    if not user_has_role(["solucionador"]):
        return "Acesso negado.", 403

    usuarios_collection.delete_one({"_id": ObjectId(user_id)})
    return redirect(url_for("listar_usuarios"))

##############################################################################
#                ROTA PARA EDIÇÃO DE SOLUÇÃO (APENAS SOLUCIONADOR)
##############################################################################

@app.route("/edit_solution/<problem_id>", methods=["GET", "POST"])
def edit_solution(problem_id):
    """
    Edição da solução de um problema já resolvido (somente 'solucionador'),
    incluindo upload/manutenção de imagens em GridFS.
    """
    if not user_is_logged_in():
        return redirect(url_for("login"))
    if not user_has_role(["solucionador"]):
        return "Acesso negado.", 403

    problema = problemas_collection.find_one({"_id": ObjectId(problem_id)})
    if not problema:
        return "Problema não encontrado.", 404
    if not problema.get("resolvido"):
        return "Problema ainda não resolvido.", 400

    if request.method == "POST":
        new_solution_json = request.form.get("solution_data", "").strip()
        try:
            new_solution_data = json.loads(new_solution_json)
        except json.JSONDecodeError:
            erro = "Erro ao interpretar dados."
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
            delete_step = request.form.get(f"deleteExistingStepImage_{i}", "false") == "true"
            step_image_file = request.files.get(f"stepImage_{i}")
            new_file_id = save_image_if_exists(step_image_file)

            old_file_id = None
            if i < len(old_steps):
                old_file_id = old_steps[i].get("stepImage")

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
            old_miniSteps = []
            if i < len(old_steps):
                old_miniSteps = old_steps[i].get("miniSteps", [])

            for j, substep in enumerate(miniSteps):
                delete_sub = request.form.get(f"deleteExistingSubStepImage_{i}_{j}", "false") == "true"
                substep_file = request.files.get(f"subStepImage_{i}_{j}")
                new_sub_file_id = save_image_if_exists(substep_file)

                old_sub_file_id = None
                if j < len(old_miniSteps):
                    old_sub_file_id = old_miniSteps[j].get("subStepImage")

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

##############################################################################
#        ROTA PARA PESQUISAR PEÇAS (ITEM_SEARCH.HTML) - APENAS CARREGA TELA
##############################################################################

@app.route("/item_search", methods=["GET"])
def item_search():
    """
    Exibe a página de pesquisa de itens (DB MachineZONE) - agora com carrinho.
    """
    if not user_is_logged_in():
        return redirect(url_for("login"))
    return render_template("item_search.html")

##############################################################################
#         ROTA /load_items - BUSCA NO BANCO MZ (MachineZONE) E RETORNA JSON
##############################################################################

ITEMS_PER_PAGE = 20

@app.route("/load_items", methods=["GET"])
def load_items():
    """
    Carrega itens via AJAX do banco MachineZONE, com possibilidade de busca.
    Armazena a pesquisa do usuário em 'history_collection', caso exista busca.
    """
    if not user_is_logged_in():
        return jsonify({"success": False, "message": "Não autorizado"}), 403

    search_query = request.args.get('search', '').strip()
    page = int(request.args.get('page', 1))
    skip_items = (page - 1) * ITEMS_PER_PAGE

    # Armazena a busca se não estiver vazia
    if search_query:
        history_collection.insert_one({
            "user_id": session["user_id"],
            "user_name": session["nome"],
            "query": search_query,
            "timestamp": datetime.now()
        })

    # Se não há busca, carrega tudo ordenado por description
    if not search_query:
        total_items = itens_collection.count_documents({})
        items_cursor = itens_collection.find({}, collation={'locale': 'pt', 'strength': 1}) \
                                       .sort('description', 1)

        all_items = list(items_cursor)
        paged_items = all_items[skip_items: skip_items + ITEMS_PER_PAGE]
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

    # Caso haja busca
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

    # Contagem total
    count_pipeline = pipeline_base + [{'$count': 'total'}]
    count_result = list(itens_collection.aggregate(
        count_pipeline,
        collation={'locale': 'pt', 'strength': 1}
    ))
    total_items = count_result[0]['total'] if count_result else 0

    # Carrega todos que deram match
    items = list(itens_collection.aggregate(
        pipeline_base,
        collation={'locale': 'pt', 'strength': 1}
    ))

    # Computa maior sub-frase
    for item in items:
        item['largest_sub_phrase_length'] = compute_largest_sub_phrase_length(
            search_tokens,
            item.get('matching_phrases', [])
        )

    # Ordenação final
    items.sort(
        key=lambda x: (
            -x['is_phrase_match'],
            -x['largest_sub_phrase_length'],
            x['description'].lower()
        )
    )

    # Paginação
    paged_items = items[skip_items: skip_items + ITEMS_PER_PAGE]
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

##############################################################################
#            ROTA PARA SERVIR IMAGENS DIRETAMENTE DO GRIDFS
##############################################################################

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
        return "Imagem não encontrada ou inválida.", 404

##############################################################################
#            ROTA PARA EXIBIR HISTÓRICO DE PESQUISAS DE ITENS
##############################################################################

@app.route("/history_search", methods=["GET"])
def history_search():
    """
    Mostra o histórico de pesquisas de todos os usuários (para PEÇAS).
    Somente 'solucionador' tem acesso.
    """
    if not user_is_logged_in():
        return redirect(url_for("login"))
    if not user_has_role(["solucionador"]):
        return "Acesso negado.", 403

    # Ordena do mais recente para o mais antigo
    all_history = list(history_collection.find({}).sort("timestamp", -1))
    return render_template("history_search.html", history=all_history)

##############################################################################
#          NOVA ROTA PARA EXIBIR HISTÓRICO DE PESQUISAS DE PROBLEMAS
##############################################################################

@app.route("/history_problem", methods=["GET"])
def history_problem():
    """
    Mostra o histórico de pesquisas de PROBLEMAS.
    Somente 'solucionador' tem acesso.
    """
    if not user_is_logged_in():
        return redirect(url_for("login"))
    if not user_has_role(["solucionador"]):
        return "Acesso negado.", 403

    # Ordena do mais recente para o mais antigo
    all_history = list(problem_history_collection.find({}).sort("timestamp", -1))
    return render_template("history_problem.html", history=all_history)

##############################################################################
#                              EXECUTAR APP
##############################################################################

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
