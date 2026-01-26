# PCM System - Gestão de Manutenção em Tempo Real

![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Django](https://img.shields.io/badge/Django-092E20?style=for-the-badge&logo=django&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)
![HTMX](https://img.shields.io/badge/HTMX-3366CC?style=for-the-badge&logo=htmx&logoColor=white)
![Bootstrap](https://img.shields.io/badge/Bootstrap-7952B3?style=for-the-badge&logo=bootstrap&logoColor=white)

## 🎯 Objetivo do Projeto

O **PCM System** é uma plataforma web robusta para o Planejamento e Controle de Manutenção (PCM) industrial. O sistema foi projetado para ser uma matriz centralizada de gestão, permitindo o controle de chamados e ordens de serviço em tempo real, desde a abertura do chamado até sua finalização.

O foco é fornecer uma visão clara e dinâmica do chão de fábrica, otimizando a alocação de recursos, reduzindo o tempo de máquina parada e melhorando a comunicação entre as equipes de produção e manutenção.

## ✨ Funcionalidades Principais

-   **Gestão de Chamados:** Usuários podem abrir chamados de manutenção, indicando a máquina, o problema e a prioridade.
-   **Triagem e Aprovação:** Gestores podem analisar os chamados, aprovando-os para gerar uma Ordem de Serviço (OS) ou recusando-os com justificativa.
-   **Dashboard em Tempo Real:**
    -   **Gráfico de Gantt:** Visualização cronológica de todas as atividades (planejadas, em execução, finalizadas e futuras), com acompanhamento dinâmico do progresso.
    -   **Kanban/Fila de Operação:** Visão clara do status de cada OS, facilitando o gerenciamento do fluxo de trabalho.
-   **Automação de Preventivas:** Cadastro de Planos de Manutenção Preventiva que geram Ordens de Serviço automaticamente com base em frequência e data.
-   **Controle de Status da OS:** Acompanhe o ciclo de vida de uma OS: `Aberta` -> `Em Execução` -> `Pausada` -> `Finalizada`.
-   **Alocação de Equipe:** Atribuição de um ou mais técnicos para cada atividade.
-   **Histórico e Logs:** Timeline detalhada com todas as interações em uma Ordem de Serviço, garantindo rastreabilidade total.
-   **Análise de Dados:** Gráficos que indicam as máquinas com maior índice de quebras, auxiliando na tomada de decisões estratégicas.
-   **Autenticação e Segurança:** Acesso restrito por login e senha.

## 🛠️ Tecnologias Utilizadas

### Backend
-   **Python:** Linguagem principal do projeto.
-   **Django:** Framework web de alto nível para um desenvolvimento rápido e seguro.
-   **Gunicorn:** Servidor WSGI para servir a aplicação em produção.

### Frontend
-   **HTML5 / CSS3:** Estrutura e estilização das páginas.
-   **Bootstrap 5:** Framework CSS para a criação de interfaces responsivas e modernas.
-   **JavaScript (Vanilla):** Para interações simples no lado do cliente.
-   **HTMX:** Permite atualizações dinâmicas da interface (AJAX) diretamente do HTML, sem a necessidade de escrever JavaScript complexo.
-   **Chart.js (implícito):** Utilizado para a renderização dos gráficos no dashboard analítico.
-   **Frappe Gantt (implícito):** Biblioteca utilizada para a construção do gráfico de Gantt interativo.

### Banco de Dados
-   **PostgreSQL:** Banco de dados relacional robusto, utilizado no ambiente de produção (via Docker).
-   **SQLite3:** Banco de dados padrão do Django, utilizado para desenvolvimento local simplificado.

### DevOps
-   **Docker & Docker Compose:** Para criar ambientes de desenvolvimento e produção consistentes e isolados através de contêineres.
-   **Variáveis de Ambiente (`.env`):** Para gerenciar configurações sensíveis (chaves de API, senhas de banco de dados) de forma segura.

## 🚀 Como Executar o Projeto

Siga os passos abaixo para configurar e rodar o ambiente de desenvolvimento localmente usando Docker.

### Pré-requisitos
-   Git
-   Docker
-   Docker Compose

### Passos para Instalação

1.  **Clone o repositório:**
    ```bash
    git clone <URL_DO_SEU_REPOSITORIO>
    cd PCM-prototipo
    ```

2.  **Crie o arquivo de variáveis de ambiente:**
    Crie um arquivo chamado `.env` na raiz do projeto e adicione as seguintes variáveis. Você pode usar os valores do `docker-compose.yml` como base.

    ```env
    SECRET_KEY=sua-chave-secreta-super-segura-aqui
    DEBUG=True
    
    # Configurações do Banco de Dados (PostgreSQL)
    DB_NAME=pcm_db
    DB_USER=pcm_user
    DB_PASSWORD=sua_senha_forte_aqui
    DB_HOST=db
    DB_PORT=5432
    ```

3.  **Suba os contêineres com Docker Compose:**
    Este comando irá construir a imagem da aplicação Django e iniciar os serviços `web` e `db`.
    ```bash
    docker-compose up --build -d
    ```

4.  **Execute as migrações do banco de dados:**
    Este comando aplica o schema do banco de dados definido nos modelos do Django.
    ```bash
    docker-compose exec web python manage.py migrate
    ```

5.  **Crie um superusuário:**
    Você precisará de um usuário administrador para acessar o painel `/admin`.
    ```bash
    docker-compose exec web python manage.py createsuperuser
    ```
    Siga as instruções no terminal para definir nome de usuário, e-mail e senha.

6.  **Acesse a aplicação:**
    Pronto! A aplicação estará disponível em:
    -   **Sistema:** http://localhost:8000
    -   **Painel Admin:** http://localhost:8000/admin

## 📂 Estrutura do Projeto

```
.
├── assets/             # App principal do Django (models, views, forms, etc.)
├── core/               # Configurações do projeto Django (settings.py, urls.py)
├── media/              # Arquivos de mídia enviados por usuários
├── static/             # Arquivos estáticos coletados pelo collectstatic
├── templates/          # Templates HTML globais
├── .env                # Arquivo com variáveis de ambiente (NÃO versionado)
├── docker-compose.yml  # Orquestração dos contêineres Docker
├── Dockerfile          # Instruções para construir a imagem da aplicação
├── manage.py           # Utilitário de linha de comando do Django
└── requirements.txt    # Dependências Python do projeto
```

