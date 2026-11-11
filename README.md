# Flex · Monitor Flexível de Passagens Aéreas

Painel responsivo em HTML/CSS/JavaScript, APIs Python Serverless na Vercel, PostgreSQL Aiven e cotações Amadeus com alertas Telegram. A operação real usa o provedor Amadeus; o modo demonstração usa dados fictícios identificados. Não realiza scraping. Repositório inicial sem layout anterior; interface criada do zero.

## O que funciona

- CRUD autenticado de rotas, duplicação, ativação e exclusão (excluir remove também o histórico).
- Qualquer código IATA de aeroporto/cidade aceito pela Amadeus; busca por nome usando sugestões da API. A disponibilidade de aeroportos e tarifas depende do provedor.
- Teto por rota e intervalo de ida de até 31 dias. Para cadastrar sete destinos em duas origens, crie as sete rotas, use **Duplicar** em cada uma e altere a origem.
- Gráfico Chart.js com pontos em timestamps reais, tooltip com segundos em Brasília, filtros por destino/período e séries por rota. Clique na legenda para ocultar origens.
- Robô consulta cada dia do intervalo, salva a menor oferta retornada por execução/rota e alerta quando o valor fica abaixo ou igual ao teto. O gráfico representa o menor preço de uma janela: a data do voo pode mudar entre consultas e aparece no tooltip.
- GitHub Actions executa a cada seis horas, no minuto 17 UTC, e manualmente. O agendador pode atrasar; em repositórios públicos, workflows agendados podem ser desativados pelo GitHub após 60 dias sem atividade.

## Prévia sem credenciais

Na tela inicial, clique em **Explorar demonstração** para abrir o painel com dados fictícios claramente identificados. É possível experimentar cadastro, duplicação, edição e filtros. Nada é salvo no banco, nenhuma API externa é chamada e nenhum alerta é enviado. Clique em **Sair** para voltar ao acesso real.

## 1. Banco Aiven

1. Crie um serviço PostgreSQL e copie a URI de conexão do painel Aiven.
2. Execute `schema.sql` no banco vazio, pelo editor SQL ou com `psql "$DATABASE_URL" -f schema.sql`. Use a porta fornecida pela Aiven, que pode diferir de 5432.
3. A URI deve incluir `sslmode=require` para criptografia. Para verificar certificado/hostname, use `sslmode=verify-full` e instale o certificado CA da Aiven, configurando `sslrootcert` na URI ou `PGSSLROOTCERT`. Não desative TLS.
4. Autorize as conexões na configuração de rede Aiven. Vercel e GitHub Actions usam saídas dinâmicas por padrão; restrições por IP exigem uma solução de saída fixa compatível com o seu plano.

O SQL é idempotente para instalação nova; não migra versões antigas de tabelas existentes. Datas de consulta são `TIMESTAMPTZ` (instantes UTC); a interface converte para Brasília. Dados monetários são NUMERIC e Decimal, sem cálculo financeiro em float no servidor.

## 2. Amadeus: cotações reais

1. Cadastre uma aplicação em [Amadeus for Developers](https://developers.amadeus.com/).
2. Ative acesso às APIs **Flight Offers Search** e **Airport & City Search**.
3. Configure `AMADEUS_CLIENT_ID`, `AMADEUS_CLIENT_SECRET` e `AMADEUS_ENV=test` inicialmente.
4. O sandbox tem cobertura e dados limitados: não use suas cotações como ofertas reais. Para monitoramento real, solicite acesso de produção, use as credenciais de produção e `AMADEUS_ENV=production` tanto na Vercel quanto no Actions.

A busca é de **ida, um adulto, em BRL**, sem reserva ou compra automática. Inclui conexões e salva o menor `grandTotal` entre as até 50 ofertas retornadas por dia, não uma garantia do menor preço de todo o mercado. Nem todas as companhias e tarifas estão disponíveis no catálogo Self-Service. Bagagem, regras, ocupação e preços devem ser conferidos antes de comprar. Não há link de reserva específico na resposta implementada.

**Consumo:** 14 rotas × 31 dias × 4 execuções = até 1.736 consultas de tarifas por dia, além de autenticação e busca por cidades. Ajuste datas e frequência aos limites/custos contratados. Falhas de um dia invalidam a cotação daquela rota nesta execução, evitando salvar um mínimo parcial como se toda a janela tivesse sido consultada.

## 3. Telegram

1. Crie um bot com [@BotFather](https://t.me/BotFather) e guarde o token.
2. Abra uma conversa com o bot e envie `/start` (ou adicione-o ao grupo desejado).
3. Consulte `getUpdates` da Bot API de forma privada para obter `message.chat.id`. Não compartilhe o token nem a URL autenticada.
4. Configure `TELEGRAM_BOT_TOKEN` e `TELEGRAM_CHAT_ID` nos Secrets do GitHub Actions.

O alerta inclui apelido, origem/destino, preço, data do voo e horário da consulta. O cooldown padrão é de 24 horas por rota, mesmo se o preço cair novamente. Falhas de envio deixam o histórico salvo e permitem nova tentativa na próxima busca. O Telegram não oferece idempotência: uma queda entre entrega e gravação pode gerar duplicidade. Ofertas abaixo do teto também aparecem no painel, independentemente da entrega do Telegram.

## 4. Publicar na Vercel

1. Importe este repositório na [Vercel](https://vercel.com/new).
2. Selecione **Other**, diretório raiz do repositório. Deixe os overrides de Build Command e Output Directory desativados. Não defina `public` como raiz: as APIs precisam estar na raiz do projeto.
3. Em **Settings → Environment Variables**, configure para Production:

| Variável | Uso |
|---|---|
| `DATABASE_URL` | URI Aiven com TLS |
| `ADMIN_TOKEN` | Segredo aleatório longo usado para acessar todas as APIs |
| `AMADEUS_CLIENT_ID` | Busca por cidade |
| `AMADEUS_CLIENT_SECRET` | Busca por cidade |
| `AMADEUS_ENV` | `test` ou `production` |

4. Faça o deploy. `vercel.json` mapeia a página pública e os assets; os arquivos `api/*.py` com classe `handler` são Functions Python. `api/common.py` e `api/amadeus.py` são módulos auxiliares, sem handlers públicos.
5. Acesse a URL e entre com seu `ADMIN_TOKEN`. Depois de alterar variáveis, faça um novo deploy.

Gere o token localmente com `python -c 'import secrets; print(secrets.token_urlsafe(32))'`. Não publique o resultado no repositório. O token fica somente no armazenamento da aba (`sessionStorage`) e sai no cabeçalho Authorization; **Sair** remove o token. É autenticação administrativa simples de um usuário, não um sistema de contas. Use apenas com HTTPS e dispositivos confiáveis. APIs sem token retornam 401; servidor sem token configurado retorna 503. Não há CORS público.

## 5. Habilitar o robô no GitHub

Em **Settings → Secrets and variables → Actions → Secrets**, adicione:

- `DATABASE_URL`
- `AMADEUS_CLIENT_ID`
- `AMADEUS_CLIENT_SECRET`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

Em **Variables**, adicione `AMADEUS_ENV` com `test` ou `production` (padrão seguro: test). Não coloque credenciais em Variables públicas. Se usar `verify-full`, configure também a instalação do CA no workflow antes da execução.

Em **Actions → Monitor de passagens → Run workflow**, execute manualmente após cadastrar uma rota. Confira os logs e o Telegram. O robô roda no Actions, não dentro de uma Function da Vercel; assim não depende dos limites de duração ou dos planos de Cron da Vercel. O GitHub precisa permitir execução de Actions no repositório.

## Desenvolvimento local

Python 3.12 recomendado:

```sh
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Preencha .env localmente; nunca faça commit dele.
python scripts/dev_server.py
# Acesse http://localhost:8000
python -m scripts.buscador_alertas
python -m unittest discover -s tests -v
```

Alternativamente, use `vercel dev` para simular o roteamento da hospedagem. O servidor local fornecido escuta apenas em 127.0.0.1 e não é um servidor de produção.

## API

Todas exigem `Authorization: Bearer SEU_ADMIN_TOKEN`.

- `GET /api/rotas`: lista rotas.
- `POST /api/rotas`: cria uma rota.
- `PUT /api/rotas`: substitui os campos da rota identificada por `id`.
- `DELETE /api/rotas?id=123`: exclui a rota e seu histórico.
- `GET /api/historico?dias=30&destino=SSA`: últimos pontos, limite de 10.000 (reduza o período se atingir o limite).
- `GET /api/aeroportos?q=Goiania`: sugestões de cidade/aeroporto via Amadeus; selecionar a sugestão preenche o IATA.

Exemplo de corpo para criar (ajuste as datas para o futuro):

```json
{"apelido":"Férias Maceió GYN","origem":"GYN","destino":"MCZ","max_preco_alerta":"950.00","ativo":true,"data_inicio":"2027-03-01","data_fim":"2027-03-07"}
```

Editar exige os mesmos campos e `id`. Ao editar uma rota, o histórico anterior permanece com origem/destino originais e o apelido atual da rota. Para comparar trajetos diferentes ao longo do tempo com clareza, duplique uma rota em vez de alterar seus aeroportos.

## Validação e limites

Testes unitários cobrem validação de rotas, autorização HTTP, parâmetros do histórico, respostas de tarifas e comportamento do robô com serviços simulados. Integração real com Aiven, Amadeus, Telegram e Vercel precisa das suas contas e credenciais; não está ativada apenas pelo código. Não envie credenciais no chat. Configure-as diretamente nos painéis dos serviços.
