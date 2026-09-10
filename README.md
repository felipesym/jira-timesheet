# Jira Sync

Ferramenta interna para replicar os apontamentos de horas do Jira do cliente no Jira da consultoria, convertendo os comentários fixos do cliente em descrições mais claras para o RH.

A execução é segura por padrão: sem `--apply`, o programa apenas mostra uma simulação e não grava nada no Jira de destino.

## O que esta versão faz

- Consulta os worklogs do usuário no Jira de origem.
- Mantém intactos os comentários exigidos no Jira do cliente.
- Classifica cada apontamento na tarefa interna correspondente.
- Gera a descrição solicitada pelo RH com:
  - `O que foi feito`
  - `Status`
  - `Entregável / Resultado`
- Usa o status real da tarefa de origem, sem presumir que ela foi concluída.
- Trata o apontamento diário de `TIRPA-560` como `Daily`.
- Remove trechos redundantes como `registro de DD/MM/AAAA`.
- Simplifica títulos longos com regras locais e, opcionalmente, com IA.
- Evita duplicar worklogs que já tenham sido enviados por esta ferramenta.
- Soma as horas existentes e planejadas de cada dia no Jira interno.
- Bloqueia como provável duplicação o lançamento que faria o dia ultrapassar 8h.

## Mapeamento das tarefas internas

- `UN-12`: Daily
- `UN-14`: Desenvolvimento
- `UN-22`: Sustentação / Hypercare
- `UN-24`: Reunião
- `UN-26`: Documentação
- `UN-27`: Apoio ao time
- `UN-31`: Testes / Homologação
- `UN-33`: Code review

Antes de usar, confirme que esse mapeamento também é válido para o integrante do time e que ele possui permissão para registrar horas nessas tarefas.

## Requisitos

- Python 3.10 ou superior
- Acesso aos dois ambientes Jira
- Token pessoal da API de cada Jira
- Opcional: chave da API da OpenAI para melhorar as descrições com IA

Cada integrante deve usar os próprios e-mails e tokens. Nunca compartilhe tokens, chaves ou o arquivo `.env`.

Esta versão usa autenticação direta nos endereços `*.atlassian.net` e, por isso, espera tokens de API Jira convencionais. Tokens Atlassian com escopos usam outro endereço de API e não são suportados por esta versão.

## Instalação

No Prompt de Comando, dentro da pasta do projeto:

```bat
py -3 -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
copy .env.example .env
```

Edite o arquivo `.env` e preencha as credenciais pessoais. Os campos `SRC_ACCOUNT_ID` e `DST_ACCOUNT_ID` podem ficar vazios; nesse caso, o script tenta identificá-los automaticamente.

## Configuração

As variáveis principais são:

- `SRC_BASE_URL`: endereço do Jira do cliente.
- `SRC_EMAIL` e `SRC_API_TOKEN`: credenciais pessoais no Jira do cliente.
- `DST_BASE_URL`: endereço do Jira da consultoria.
- `DST_EMAIL` e `DST_API_TOKEN`: credenciais pessoais no Jira da consultoria.
- `OPENAI_API_KEY`: opcional; necessária somente ao ativar a IA.
- `OPENAI_MODEL`: modelo usado para revisar os textos.
- `WEEKS_BACK`: quantidade de semanas de calendário incluídas quando datas explícitas não forem informadas. O valor padrão `2` significa a semana atual e a semana anterior.

O único arquivo dotenv carregado pelo script é o `.env` localizado ao lado de `jira_sync.py`. Ele reúne as credenciais dos dois Jiras, `OPENAI_API_KEY` e `OPENAI_MODEL`.

O arquivo `.env` é ignorado pelo Git e não deve ser enviado ao repositório.

## Menu de execução

Depois da instalação e configuração, é possível usar o menu sem digitar os comandos manualmente: abra `executar_jira_sync.bat` com duplo clique.

O menu oferece:

1. Aplicar e gravar os apontamentos no Jira interno.
2. Mostrar a ajuda do script.
0. Sair.

Ao abrir o `.bat`, uma janela identificada como **Jira Sync** mostra o início da execução. Se o Python não for encontrado, estiver abaixo da versão 3.10 ou ocorrer qualquer erro antes de abrir o menu, a janela permanece aberta para que a mensagem possa ser lida. Pressione uma tecla somente depois de anotar ou corrigir o erro apresentado.

As opções de simulação (com ou sem IA, período específico, exportação em planilha) continuam disponíveis pela linha de comando, conforme a seção "Uso recomendado" abaixo, mas não aparecem no menu do `.bat`.

A opção **APLICAR** permite escolher o período e o uso de IA. Depois do aviso de segurança, basta pressionar Enter para iniciar. Se qualquer texto for digitado — por exemplo, `CANCELAR` — a aplicação é cancelada. Antes da consulta e da gravação, o console mostra uma mensagem indicando o início do processamento.

Os relatórios exibidos diretamente no console seguem o estilo visual da primeira versão: separadores por dia, ícones, campos recuados e um resumo final. Isso não altera as regras de duplicidade, o limite de 8 horas ou o conteúdo que será enviado ao Jira.

## Uso recomendado

Primeiro, simule um período específico sem IA:

```bash
python3 jira_sync.py --start 2026-09-07 --end 2026-09-13 --no-ai
```

Compare com a versão usando IA:

```bash
python3 jira_sync.py --start 2026-09-07 --end 2026-09-13 --ai
```

Para salvar uma simulação em planilha pela linha de comando, acrescente `--output-xlsx`:

```bash
python3 jira_sync.py --start 2026-09-07 --end 2026-09-13 --ai \
  --output-xlsx relatorios/minha_simulacao.xlsx
```

`--output-xlsx` é exclusivo para simulação e não pode ser combinado com `--apply`.

Revise os itens, as horas e os destinos apresentados. Somente depois da conferência, grave no Jira interno:

```bash
python3 jira_sync.py --start 2026-09-07 --end 2026-09-13 --ai --apply
```

Também é possível omitir `--ai` e `--no-ai`; em uso interativo o script pergunta se deve usar IA. Em execução automatizada, a IA fica desativada por padrão.

Quando `--start` e `--end` não são informados, o período padrão vai da segunda-feira da semana anterior até o domingo da semana atual. Dias futuros naturalmente não terão apontamentos.

## Controle diário de 8 horas

Quando as credenciais do Jira interno estão configuradas, o script consulta os apontamentos existentes do próprio usuário em todas as tarefas visíveis no Jira interno. Para cada novo registro, mostra o total acumulado daquele dia.

Se um lançamento fizer o total projetado ultrapassar 8h:

- ele recebe o status `probable_duplicate`;
- a tela mostra `PROVÁVEL DUPLICAÇÃO` e os totais atual e projetado;
- o lançamento é bloqueado e não é enviado ao Jira interno;
- os demais registros continuam sendo analisados normalmente.

Um total exatamente igual a 8h é permitido. Na simulação sem acesso ao Jira interno, o programa avisa que o total considera apenas os itens da própria execução.

## Cuidados antes de aplicar

- Sempre execute uma simulação antes de usar `--apply`.
- Confirme as datas, o total de horas e as tarefas de destino.
- Aguarde cerca de dois minutos após o último apontamento em qualquer um dos dois ambientes Jira antes de sincronizar. A API de atualizações do Jira pode não devolver alterações feitas no minuto imediatamente anterior.
- Não execute simultaneamente em dois computadores com a mesma conta.
- Faça o primeiro teste com um intervalo pequeno, de preferência um único dia.

## Limitações conhecidas

- A prevenção de duplicidade reconhece os worklogs criados por esta ferramenta por meio de um marcador próprio. Um lançamento feito manualmente no Jira interno não é automaticamente reconhecido como equivalente.
- Se um apontamento já sincronizado for corrigido no Jira do cliente, a versão existente no Jira interno não é atualizada. A correção deve ser feita manualmente no destino ou tratada antes de uma nova sincronização.
- A classificação depende dos comentários e títulos disponíveis no Jira de origem. Itens não reconhecidos aparecem na simulação como `SEM MAPEAMENTO` e não devem ser aplicados sem revisão.
- O limite de 8h considera os apontamentos do usuário que estejam visíveis para a conta usada no Jira interno. Restrições de projeto, tarefa ou visibilidade do worklog podem impedir a API de devolver algum registro.
- A sincronização é unidirecional: cliente para consultoria.

## Uso de IA e privacidade

Quando a IA está ativada, o script envia à API da OpenAI apenas o conteúdo necessário para revisar a descrição: categoria, título da tarefa, título da tarefa pai, rascunho local e status. Chaves e URLs do Jira não fazem parte da solicitação, e a chamada usa `store: false`.

Se a API de IA falhar ou devolver um resultado inválido, o script preserva a descrição gerada localmente.

## Segurança

- Não publique `.env`, tokens, chaves, exportações JSON ou relatórios XLSX/CSV.
- Revogue imediatamente qualquer credencial que seja exposta.
- Use somente tokens pessoais e mantenha o repositório privado.
- Relatórios reais do cliente não fazem parte deste repositório.

## Evolução das versões

- **Versão original:** replicação básica dos worklogs do Jira do cliente para o Jira interno.
- **Versão 2:** descrições internas mais claras, regras de simplificação, tratamento especial da Daily, modo opcional de IA e prevenção de duplicidade por worklog de origem.
- **Versão 3 (atual):** formato estruturado pedido pelo RH, incluindo atividade realizada, status real e entregável/resultado. Mantém o modo de simulação como padrão, oferece IA opcional, controla o limite diário de 8h e inclui menu de execução para Windows.
