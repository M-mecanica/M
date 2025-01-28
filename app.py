from flask import Flask, render_template, request, redirect, url_for, session
from pymongo import MongoClient
from bson.objectid import ObjectId
import json

app = Flask(__name__)
app.secret_key = "CHAVE_SECRETA_PARA_SESSAO"  # Troque por algo seguro em produção

# Conexão com MongoDB (ajuste a URI conforme seu ambiente)
client = MongoClient("mongodb://localhost:27017/")
db = client["m_plataforma"]

# Coleções utilizadas
problemas_collection = db["problemas"]
usuarios_collection = db["usuarios"]

##########################################
#            FUNÇÕES DE SUPORTE
##########################################

def user_is_logged_in():
    """Retorna True se há um usuário logado na sessão."""
    return "user_id" in session

def user_has_role(roles_permitidos):
    """
    Verifica se o usuário logado possui um dos papéis informados em 'roles_permitidos'.
    Ex.: user_has_role(['solucionador']).
    """
    if not user_is_logged_in():
        return False
    return session.get("role") in roles_permitidos

##########################################
#        ROTA RAIZ (REDIRECIONA)
##########################################

@app.route("/")
def root():
    """
    Ao acessar a rota raiz, se o usuário estiver logado, redireciona para /index.
    Caso contrário, redireciona para /login.
    """
    if user_is_logged_in():
        return redirect(url_for("index"))
    return redirect(url_for("login"))

##########################################
#             ROTA DE LOGIN
##########################################

@app.route("/login", methods=["GET", "POST"])
def login():
    """
    Exibe o formulário de login (GET) e processa o login (POST).
    Ao logar com sucesso, direciona para /index.
    """
    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        senha = request.form.get("senha", "").strip()

        usuario = usuarios_collection.find_one({"nome": nome, "senha": senha})
        if usuario:
            # Define dados na sessão
            session["user_id"] = str(usuario["_id"])
            session["nome"] = usuario["nome"]
            session["role"] = usuario["role"]
            return redirect(url_for("index"))
        else:
            erro = "Usuário ou senha inválidos!"
            return render_template("login.html", erro=erro)
    # GET - apenas renderiza o template de login
    return render_template("login.html", erro=None)

##########################################
#             ROTA DE REGISTER
##########################################

@app.route("/register", methods=["GET", "POST"])
def register():
    """
    Cria um novo usuário na plataforma.
    Roles possíveis (exemplo): 'comum', 'solucionador', 'mecanico' etc.
    """
    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        senha = request.form.get("senha", "").strip()
        role = request.form.get("role", "comum").strip()

        # Verifica se já existe um usuário com este nome
        usuario_existente = usuarios_collection.find_one({"nome": nome})
        if usuario_existente:
            erro = "Usuário já existe!"
            return render_template("register.html", erro=erro)

        # Cria e insere o novo usuário (MVP: sem hash de senha)
        usuario = {
            "nome": nome,
            "senha": senha,
            "role": role
        }
        usuarios_collection.insert_one(usuario)
        return redirect(url_for("login"))

    # GET - apenas renderiza o template de registro
    return render_template("register.html", erro=None)

##########################################
#             ROTA DE LOGOUT
##########################################

@app.route("/logout", methods=["GET"])
def logout():
    """
    Encerra a sessão do usuário atual.
    """
    session.clear()
    return redirect(url_for("login"))

##########################################
#             ROTA DE INDEX
##########################################

@app.route("/index", methods=["GET"])
def index():
    """
    Página inicial do usuário logado. Se não estiver logado, redireciona para /login.
    """
    if not user_is_logged_in():
        return redirect(url_for("login"))
    return render_template("index.html")

##########################################
#           ROTA DE PESQUISA
##########################################

@app.route("/search", methods=["GET"])
def search():
    """
    Pesquisa problemas resolvidos com base em um termo (q).
    Se não houver termo, mostra todos os resolvidos.
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

    return render_template("resultados.html", problemas=problemas_encontrados, termo_busca=termo_busca)

##########################################
#       ROTA PARA ADICIONAR PROBLEMA
##########################################

@app.route("/add", methods=["GET", "POST"])
def add_problem():
    """
    Permite cadastrar um novo problema no sistema (não resolvido).
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

##########################################
#       ROTA PARA LISTAR NÃO RESOLVIDOS
##########################################

@app.route("/unresolved", methods=["GET"])
def unresolved():
    """
    Lista todos os problemas que ainda não foram marcados como resolvidos.
    """
    if not user_is_logged_in():
        return redirect(url_for("login"))

    query = {"resolvido": False}
    problemas_nao_resolvidos = list(problemas_collection.find(query))
    for p in problemas_nao_resolvidos:
        p["_id_str"] = str(p["_id"])

    return render_template("nao_resolvidos.html", problemas=problemas_nao_resolvidos)

##########################################
#   ROTA PARA EXIBIR FORM DE RESOLVER
##########################################

@app.route("/resolver_form/<problem_id>", methods=["GET"])
def resolver_form(problem_id):
    """
    Exibe o formulário 'resolver.html' para o usuário inserir
    passos e sub-passos da solução.
    Somente 'solucionador' pode acessar.
    """
    if not user_is_logged_in():
        return redirect(url_for("login"))
    if not user_has_role(["solucionador"]):
        return "Acesso negado. Você não tem permissão para resolver problemas.", 403

    return render_template("resolver.html", problem_id=problem_id)

##########################################
#   ROTA PARA MARCAR PROBLEMA COMO RESOLVIDO
##########################################

@app.route("/resolver/<problem_id>", methods=["POST"])
def resolver_problema(problem_id):
    """
    Recebe a estrutura (JSON) de passos e sub-passos,
    e marca o problema como resolvido no banco.
    Somente 'solucionador' pode fazer isso.
    """
    if not user_is_logged_in():
        return redirect(url_for("login"))
    if not user_has_role(["solucionador"]):
        return "Acesso negado. Você não tem permissão para resolver problemas.", 403

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

##########################################
#   ROTA PARA EXIBIR SOLUÇÃO
##########################################

@app.route("/solucao/<problem_id>", methods=["GET"])
def exibir_solucao(problem_id):
    """
    Exibe a página 'solucao.html' com animação da solução,
    apenas se resolvido.
    """
    if not user_is_logged_in():
        return redirect(url_for("login"))

    problema = problemas_collection.find_one({"_id": ObjectId(problem_id)})
    if not problema:
        return "Problema não encontrado.", 404
    if not problema.get("resolvido"):
        return "Este problema ainda não está marcado como resolvido.", 400

    solucao = problema.get("solucao", {})
    return render_template("solucao.html", problema=problema, solucao=solucao)

##########################################
#   ROTA PARA DELETAR PROBLEMA
##########################################

@app.route("/delete/<problem_id>", methods=["POST"])
def delete_problem(problem_id):
    """
    Permite que apenas 'solucionador' exclua um problema.
    """
    if not user_is_logged_in():
        return redirect(url_for("login"))
    if not user_has_role(["solucionador"]):
        return "Acesso negado. Você não tem permissão para deletar problemas.", 403

    problema = problemas_collection.find_one({"_id": ObjectId(problem_id)})
    if not problema:
        return "Problema não encontrado.", 404

    problemas_collection.delete_one({"_id": ObjectId(problem_id)})

    if problema["resolvido"]:
        return redirect(url_for("search"))
    else:
        return redirect(url_for("unresolved"))

##########################################
#   ROTA PARA EDIÇÃO INLINE (OPCIONAL)
##########################################

@app.route("/inline_edit/<problem_id>", methods=["POST"])
def inline_edit_problem(problem_id):
    """
    Edita título e descrição (versão inline).
    Somente 'solucionador' pode editar.
    """
    if not user_is_logged_in():
        return redirect(url_for("login"))
    if not user_has_role(["solucionador"]):
        return "Acesso negado. Você não tem permissão para editar problemas.", 403

    titulo_novo = request.form.get("titulo", "").strip()
    descricao_nova = request.form.get("descricao", "").strip()

    if not titulo_novo or not descricao_nova:
        return redirect(url_for("search"))

    problema = problemas_collection.find_one({"_id": ObjectId(problem_id)})
    if not problema:
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

##########################################
#   ROTA PARA LISTAR E DELETAR USUÁRIOS
##########################################

@app.route("/usuarios", methods=["GET"])
def listar_usuarios():
    """
    Lista todos os usuários registrados.
    Somente 'solucionador' pode acessar.
    """
    if not user_is_logged_in():
        return redirect(url_for("login"))
    if not user_has_role(["solucionador"]):
        return "Acesso negado. Você não tem permissão para gerenciar usuários.", 403

    # Busca todos os usuários
    usuarios = list(usuarios_collection.find({}))
    # Garante que o "_id" seja string
    for u in usuarios:
        u["_id_str"] = str(u["_id"])

    return render_template("registros.html", usuarios=usuarios)

@app.route("/delete_user/<user_id>", methods=["POST"])
def delete_user(user_id):
    """
    Deleta um usuário do sistema, somente se for 'solucionador'.
    """
    if not user_is_logged_in():
        return redirect(url_for("login"))
    if not user_has_role(["solucionador"]):
        return "Acesso negado. Você não tem permissão para gerenciar usuários.", 403

    usuarios_collection.delete_one({"_id": ObjectId(user_id)})
    return redirect(url_for("listar_usuarios"))

##########################################
#   ROTA PARA EDITAR SOLUÇÃO (NOVO)
##########################################

@app.route("/edit_solution/<problem_id>", methods=["GET", "POST"])
def edit_solution(problem_id):
    """
    Permite que o solucionador edite a solução de um problema já resolvido,
    mas de forma gráfica, sem exibir JSON cru.
    """
    # Verifica login
    if not user_is_logged_in():
        return redirect(url_for("login"))
    # Verifica role
    if not user_has_role(["solucionador"]):
        return "Acesso negado. Você não tem permissão para editar soluções.", 403

    problema = problemas_collection.find_one({"_id": ObjectId(problem_id)})
    if not problema:
        return "Problema não encontrado.", 404
    if not problema.get("resolvido"):
        return "Este problema ainda não foi marcado como resolvido.", 400

    if request.method == "POST":
        # Aqui, recebemos o JSON gerado pelo JavaScript
        new_solution_json = request.form.get("solution_data", "").strip()
        try:
            new_solution_data = json.loads(new_solution_json)
        except json.JSONDecodeError:
            # Caso o JSON esteja inválido, podemos mostrar um erro
            erro = "Houve um erro ao interpretar os dados. Tente novamente."
            return render_template("edit_solution.html",
                                   problema=problema,
                                   solucao=problema.get("solucao", {}),
                                   erro=erro)

        # Atualiza no banco de dados
        problemas_collection.update_one(
            {"_id": ObjectId(problem_id)},
            {"$set": {"solucao": new_solution_data}}
        )

        # Redireciona de volta para a página de exibição da solução
        return redirect(url_for("exibir_solucao", problem_id=problem_id))

    # GET: Renderiza o formulário de edição
    # Buscamos a solução existente (se existir)
    solucao_atual = problema.get("solucao", {})
    # Se não houver "passos", definimos como lista vazia
    passos = solucao_atual.get("passos", [])

    return render_template("edit_solution.html",
                           problema=problema,
                           passos=passos,
                           erro=None)


##########################################
#         EXECUÇÃO DA APLICAÇÃO
##########################################

if __name__ == "__main__":
    # Em produção, use debug=False e uma SECRET_KEY robusta
    app.run(debug=True)
