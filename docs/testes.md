# Registro dos testes

## Testes automatizados

Comando: `python3 -m unittest discover -s tests -v`

Resultado registrado: 11 testes passaram no Python 3.12. A suíte usa respostas simuladas do Moodle e do SMTP para verificar a seleção de tarefas e alunos, o conteúdo do lembrete, as retentativas, o encaminhamento para a fila de falhas e o descarte de duplicatas.

## Testes de aceite

Executados em 17/11/2026 no ambiente local com Docker Compose, Moodle, RabbitMQ e Mailpit, usando contas fictícias no curso **Engenharia de Software II - Teste**.

| Caso | Resultado observado | Evidência | Status |
|---|---|---|---|
| 1. Envio do lembrete | Ana recebeu o lembrete da **Atividade de teste**, com o prazo em horário de Brasília. O link do e-mail abriu a atividade correta no Moodle. | [Print do Mailpit](caso-1-mailpit.png) | Aprovado |
| 2. Filtro de alunos e tarefas | Bruno já havia entregado a **Atividade de teste** e não recebeu lembrete. As atividades **Sem prazo**, **Vencida** e **Prazo distante** não geraram e-mails durante a verificação. A caixa continuou com apenas o lembrete original da Ana. | [Print do Mailpit](caso-2-mailpit.png) | Aprovado |
| 3. Bloqueio de duplicatas | Após recriar o contêiner de `notificacoes`, o serviço registrou o mesmo lembrete como duplicado e o Mailpit não recebeu outra cópia. | [Print do Mailpit](caso-3-mailpit.png) e log abaixo | Aprovado |
| 4. Retentativa após falha | Com o Mailpit parado, o envio da atividade **Teste de falha** falhou nas tentativas 1 e 2. Após religar o Mailpit, o lembrete foi enviado para a Ana na terceira tentativa. | [Print do Mailpit](caso-4-mailpit.png) e log abaixo | Aprovado |
| 5. Persistência após recriação | Após `docker compose down` sem `-v` e `docker compose up -d`, o curso, as atividades e a entrega do Bruno permaneceram no Moodle. O serviço reconheceu o lembrete anterior como duplicado, sem registrar novo envio para ele no log verificado. | [Print do Moodle](caso-5-moodle.png) e log abaixo | Aprovado |

## Trechos dos logs

**Caso 3 — duplicata após recriar `notificacoes`:**

```text
INFO:root:id=2:1:3 tentativa=1 resultado=duplicado
```

**Caso 4 — falhas de SMTP e envio na terceira tentativa:**

```text
WARNING:root:Falha SMTP: id=2:5:3 tentativa=1 tipo=gaierror detalhe=[Errno -3] Temporary failure in name resolution
WARNING:root:Falha SMTP: id=2:5:3 tentativa=2 tipo=gaierror detalhe=[Errno -3] Temporary failure in name resolution
INFO:root:id=2:5:3 tentativa=3 resultado=enviado
```

**Caso 5 — histórico de envio preservado após recriar o ambiente:**

```text
INFO:root:id=2:5:3 tentativa=1 resultado=duplicado
```

A caixa do Mailpit deixou de exibir mensagens anteriores após o ambiente ser recriado. Os prints registram os e-mails recebidos durante os testes, e o log do caso 5 confirma que o serviço de notificações preservou o registro do envio.
