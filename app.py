# app.py

"""
Aplicação Flask unificada que utiliza DOIS bancos de dados MongoDB:
1) 'm_plataforma' (M) - Para cadastro/resolução de problemas mecânicos
2) 'MachineZONE' (MZ) - Para pesquisa de itens (rolamentos, etc.)

- Login/Logout e gerenciamento de usuários (coleção 'usuarios') ficam no DB 'm_plataforma'.
- Pesquisa de itens (/load_items) e lógica associada usam o DB 'MachineZONE'.

Obs.: Ajuste credenciais de conexão e secret_key conforme sua necessidade.
"""

import os
import uuid
import json
import re
import unicodedata
import datetime

from flask import (
    Flask, render_template, request, redirect,
    url_for, session, jsonify
)
from pymongo import MongoClient
from bson.objectid import ObjectId
from werkzeug.utils import secure_filename

##############################################################################
#                           CONFIGURAÇÕES FLASK
##############################################################################

app = Flask(__name__)
app.secret_key = "CHAVE_SECRETA_PARA_SESSAO"  # Troque por algo seguro em produção

# Pasta de upload de imagens (caso precise para soluções de problemas)
app.config['UPLOAD_FOLDER'] = 'static/uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

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

# ------------------------ DB do MZ (MachineZONE) ----------------------------
client_mz = MongoClient(
    "mongodb+srv://adaltonmuzilomendes:rolamento@cluster0.atmeh.mongodb.net/"
)
db_mz = client_mz["MachineZONE"]

# Coleção principal de itens no MZ
itens_collection = db_mz["itens"]
# (Se precisar, inclua demais coleções como suppliers, customers, etc.)

##############################################################################
#                    FUNÇÕES AUXILIARES (UPLOAD, LOGIN ETC.)
##############################################################################

def user_is_logged_in():
    """Retorna True se há um usuário logado na sessão (banco 'm_plataforma')."""
    return "user_id" in session

def user_has_role(roles_permitidos):
    """
    Verifica se o usuário logado possui um dos papéis em 'roles_permitidos'.
    Ex.: user_has_role(['solucionador', 'mecanico']).
    """
    if not user_is_logged_in():
        return False
    return session.get("role") in roles_permitidos

def save_image_if_exists(file_obj):
    """
    Recebe um objeto FileStorage (upload de imagem) e salva em 'static/uploads',
    retornando o caminho relativo para uso. Retorna None se não houver arquivo.
    """
    if not file_obj or file_obj.filename.strip() == "":
        return None

    filename = secure_filename(file_obj.filename)
    ext = os.path.splitext(filename)[1]
    unique_name = f"{uuid.uuid4()}{ext}"

    save_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_name)
    file_obj.save(save_path)

    return os.path.join(app.config['UPLOAD_FOLDER'], unique_name)

##############################################################################
#           FUNÇÕES DE NORMALIZAÇÃO E AVALIAÇÃO (PARA BUSCA MZ)
##############################################################################

def normalize_string(s):
    """
    Remove acentos e deixa tudo minúsculo.
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
    Ao acessar a rota raiz, se o usuário estiver logado, vai para /index.
    Caso contrário, vai para /login.
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
            # Define dados de sessão
            session["user_id"] = str(usuario["_id"])
            session["nome"] = usuario["nome"]
            session["role"] = usuario["role"]
            return redirect(url_for("index"))
        else:
            erro = "Usuário ou senha inválidos."
            return render_template("login.html", erro=erro)

    # GET
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
        role = request.form.get("role", "comum").strip()

        # Verifica se usuário já existe
        if usuarios_collection.find_one({"nome": nome}):
            erro = "Usuário já existe!"
            return render_template("register.html", erro=erro)

        novo_usuario = {
            "nome": nome,
            "senha": senha,  # Em produção: use hash/criptografia
            "role": role
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
    Pesquisa problemas resolvidos com base num termo (q). Se vazio, mostra todos resolvidos.
    """
    if not user_is_logged_in():
        return redirect(url_for("login"))

    termo_busca = request.args.get("q", "").strip()
    if termo_busca:
        query = {
            "titulo": {"$regex": termo_busca, "$options": "i"},
            "resolvido": True
        }
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
    Cadastra novo problema (não resolvido).
    """
    if not user_is_logged_in():
        return redirect(url_for("login"))

    if request.method == "POST":
        titulo = request.form.get("titulo", "").strip()
        descricao = request.form.get("descricao", "").strip()

        if titulo and descricao:
            problema = {
                "titulo": titulo,
                "descricao": descricao,
                "resolvido": False
            }
            problemas_collection.insert_one(problema)
            return redirect(url_for("unresolved"))
        else:
            return render_template("add.html", erro="Preencha todos os campos.")
    return render_template("add.html", erro=None)

@app.route("/unresolved", methods=["GET"])
def unresolved():
    """
    Lista problemas que ainda não foram marcados como resolvidos.
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
    Exibe formulário para resolver um problema (somente roles 'solucionador' ou 'mecanico').
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
    Exibe a página 'solucao.html' com a solução do problema (se resolvido).
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
    Deleta um problema (somente 'solucionador' pode).
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

@app.route("/inline_edit/<problem_id>", methods=["POST"])
def inline_edit_problem(problem_id):
    """
    Edição rápida de título e descrição (somente 'solucionador').
    """
    if not user_is_logged_in():
        return redirect(url_for("login"))
    if not user_has_role(["solucionador"]):
        return "Acesso negado.", 403

    titulo_novo = request.form.get("titulo", "").strip()
    descricao_nova = request.form.get("descricao", "").strip()

    if not titulo_novo or not descricao_nova:
        return redirect(url_for("search"))

    if not problemas_collection.find_one({"_id": ObjectId(problem_id)}):
        return "Problema não encontrado.", 404

    problemas_collection.update_one(
        {"_id": ObjectId(problem_id)},
        {
            "$set": {
                "titulo": titulo_novo,
                "descricao": descricao_nova
            }
        }
    )
    return redirect(url_for("search"))

@app.route("/usuarios", methods=["GET"])
def listar_usuarios():
    """
    Lista todos os usuários (somente 'solucionador').
    """
    if not user_is_logged_in():
        return redirect(url_for("login"))
    if not user_has_role(["solucionador"]):
        return "Acesso negado.", 403

    usuarios = list(usuarios_collection.find({}))
    for u in usuarios:
        u["_id_str"] = str(u["_id"])

    return render_template("registros.html", usuarios=usuarios)

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

@app.route("/edit_solution/<problem_id>", methods=["GET", "POST"])
def edit_solution(problem_id):
    """
    Edição da solução de um problema já resolvido (somente 'solucionador'),
    podendo incluir upload de imagens.
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

        # Faz upload de imagens (se existirem) para cada passo e subpasso
        steps = new_solution_data.get("steps", [])
        for i, step in enumerate(steps):
            step_file_key = f"stepImage_{i}"
            step_image_file = request.files.get(step_file_key)
            saved_path = save_image_if_exists(step_image_file)
            if saved_path:
                step["stepImage"] = saved_path

            miniSteps = step.get("miniSteps", [])
            for j, substep in enumerate(miniSteps):
                substep_file_key = f"subStepImage_{i}_{j}"
                substep_image_file = request.files.get(substep_file_key)
                saved_sub_path = save_image_if_exists(substep_image_file)
                if saved_sub_path:
                    substep["subStepImage"] = saved_sub_path

        # Atualiza a solução no banco
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
#    ROTA PARA PESQUISAR PEÇAS (ITEM_SEARCH.HTML) - APENAS CARREGA TELA
##############################################################################

@app.route("/item_search", methods=["GET"])
def item_search():
    """
    Exibe a página de pesquisa de itens (integra com DB MachineZONE).
    Utiliza o template 'item_search.html', onde foi ajustado o botão de voltar
    para usar 'url_for("index")' em vez de 'index.html'.
    """
    if not user_is_logged_in():
        return redirect(url_for("login"))
    return render_template("item_search.html")

##############################################################################
#       ROTA /load_items - BUSCA NO BANCO MZ (MachineZONE) E RETORNA JSON
##############################################################################

ITEMS_PER_PAGE = 20  # Quantidade de itens por página

@app.route("/load_items", methods=["GET"])
def load_items():
    """
    Carrega itens via AJAX do banco 'MachineZONE'.
    Ordenação:
      1) is_phrase_match (desc)
      2) maior sub-frase (desc)
      3) description (asc)
    Retorna JSON: { items: [...], has_more: bool, total_items: int }
    """
    if not user_is_logged_in():
        # Caso queira bloquear pesquisa para não logados. Senão, retire esta checagem.
        return jsonify({"success": False, "message": "Não autorizado"}), 403

    search_query = request.args.get('search', '').strip()
    page = int(request.args.get('page', 1))
    skip_items = (page - 1) * ITEMS_PER_PAGE

    # Se não há busca, carrega tudo (ordenado por description)
    if not search_query:
        total_items = itens_collection.count_documents({})
        items_cursor = itens_collection.find({}, collation={'locale': 'pt', 'strength': 1}) \
                                       .sort('description', 1)

        all_items = list(items_cursor)
        paged_items = all_items[skip_items : skip_items + ITEMS_PER_PAGE]
        has_more = (len(paged_items) == ITEMS_PER_PAGE)

        items_list = []
        for item in paged_items:
            items_list.append({
                '_id': str(item['_id']),
                'description': item.get('description', ''),
                'stock_mz': item.get('stock_mz', 0),
                'stock_eld': item.get('stock_eld', 0),
                'price': float(item.get('price', 0.0)),
                # Sem destaque => 'is_highlighted' = 0
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

    # is_phrase_match
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

    # Faz contagem
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

    # Computa largest_sub_phrase_length
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
    paged_items = items[skip_items : skip_items + ITEMS_PER_PAGE]
    has_more = (len(paged_items) == ITEMS_PER_PAGE)

    # Monta retorno
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
#            (Opcional) ROTAS DE HIGHLIGHT / UNHIGHLIGHT (MZ)
##############################################################################

@app.route("/highlight_item", methods=["POST"])
def highlight_item():
    """
    Marca a 'matching_phrases' no item do DB MZ, usando a frase de busca.
    Deixamos caso queira "demarcar" manualmente, mas aqui não há botões front-end.
    """
    if not user_is_logged_in():
        return jsonify({'success': False, 'message': 'Não autorizado'}), 403

    data = request.get_json()
    item_id = data.get('item_id')
    search_phrase = data.get('search_phrase', '').strip()

    if not search_phrase:
        return jsonify({'success': False, 'message': 'Frase vazia'}), 400
    try:
        normalized = normalize_string(search_phrase)
        itens_collection.update_one(
            {'_id': ObjectId(item_id)},
            {'$addToSet': {'matching_phrases': normalized}}
        )
        # Opcionalmente atualiza as 'tags' com tokens da frase
        item = itens_collection.find_one({'_id': ObjectId(item_id)})
        if item:
            current_tags = set(item.get('tags', []))
            words = normalized.split()
            for w in words:
                current_tags.add(w)
            itens_collection.update_one(
                {'_id': ObjectId(item_id)},
                {'$set': {'tags': sorted(current_tags)}}
            )
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route("/unhighlight_item", methods=["POST"])
def unhighlight_item():
    """
    Remove a 'matching_phrases' do item do DB MZ, usando a frase de busca.
    """
    if not user_is_logged_in():
        return jsonify({'success': False, 'message': 'Não autorizado'}), 403

    data = request.get_json()
    item_id = data.get('item_id')
    search_phrase = data.get('search_phrase', '').strip()

    try:
        normalized = normalize_string(search_phrase)
        itens_collection.update_one(
            {'_id': ObjectId(item_id)},
            {'$pull': {'matching_phrases': normalized}}
        )
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

##############################################################################
#                              EXECUTAR APP
##############################################################################

if __name__ == "__main__":
    # Em produção, use debug=False e forneça SECRET_KEY robusta no servidor
    app.run(host="0.0.0.0", port=5000, debug=True)
