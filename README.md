# Reengajamento no Moodle

Projeto de Engenharia de Software II da PUCRS — 2026/2.

O projeto envia lembretes a estudantes que têm uma atividade pendente no Moodle e cujo prazo vence nas próximas 24 horas. No ambiente local, os e-mails aparecem no Mailpit.

## Como funciona

- **Acompanhamento:** consulta as atividades e as entregas no Moodle pela API REST. Quando encontra uma pendência dentro do prazo, publica uma solicitação no RabbitMQ.
- **Notificações:** lê a fila e envia o lembrete por SMTP. O e-mail traz o nome da atividade, o prazo no horário de Brasília e o link para o Moodle.
- **Histórico de envios:** depois de um envio bem-sucedido, o serviço registra o curso, a atividade e o aluno no SQLite. Se a mesma solicitação chegar de novo, ela é descartada como duplicada.

Atividades sem prazo, vencidas ou que ainda não abriram ficam de fora. Quem já enviou a tentativa atual não recebe lembrete. Um rascunho ainda conta como pendência. O projeto foi testado com atividades individuais visíveis para toda a turma.

Se o SMTP falhar, o serviço tenta enviar novamente após 15 segundos, até três tentativas por mensagem. Se todas falharem, a mensagem vai para a fila `lembretes.falhas`. Uma consulta posterior pode gerar outra solicitação se a atividade continuar elegível. Se o serviço cair entre o envio do e-mail e o registro no SQLite, pode ocorrer um reenvio.

## Como rodar localmente

É preciso ter Docker com Docker Compose v2 e acesso à internet para baixar as imagens e o código do Moodle.

### 1. Subir o ambiente

Na pasta do projeto, copie o arquivo de exemplo se você ainda não tiver um `.env`:

```bash
cp -n .env.example .env
```

Na primeira instalação, defina uma senha local em `POSTGRES_PASSWORD` no `.env`. Depois, execute:

```bash
docker compose up -d --build moodle rabbitmq mailpit
```

### 2. Instalar o Moodle

Faça esta etapa apenas na primeira instalação. No Bash, execute:

```bash
docker compose exec -u www-data moodle cp /opt/moodle-config.php /var/moodle-state/config.php

read -rsp 'Senha do administrador do Moodle: ' SENHA_MOODLE
echo
docker compose exec -u www-data moodle php admin/cli/install_database.php \
  --agree-license \
  --fullname="Moodle de testes" \
  --shortname="Moodle teste" \
  --adminuser=admin \
  --adminpass="$SENHA_MOODLE" \
  --adminemail=admin@example.test
unset SENHA_MOODLE
```

Se o instalador disser que `config.php` não existe mesmo após a cópia, execute o comando abaixo e repita apenas a instalação do banco:

```bash
docker compose exec -u root moodle cp --remove-destination \
  /var/moodle-state/config.php /var/www/html/config.php
```

Abra o [Moodle](http://localhost:8080), entre como `admin` e crie um curso de teste. Matricule dois alunos fictícios e crie uma atividade com prazo para cerca de duas horas à frente. Para testar o filtro, faça a entrega com um aluno e deixe a do outro pendente.

### 3. Configurar a integração

Na administração do Moodle, habilite **Enable web services** em **Advanced features** e ative o protocolo **REST** em **Server → Web services → Manage protocols**.

Crie um serviço externo habilitado e restrito a usuários autorizados. Adicione estas funções:

- `mod_assign_get_assignments`
- `core_enrol_get_enrolled_users`
- `mod_assign_get_submissions`

Crie um usuário para a integração, matricule-o como professor no curso de teste e conceda a ele a permissão `webservice/rest:use`. Adicione esse usuário aos autorizados do serviço e gere um token em **Manage tokens**. A consulta de matrículas precisa trazer os campos `roles` e `email`.

No `.env`, preencha `MOODLE_TOKEN` com o token e `MOODLE_COURSE_ID` com o número que aparece em `course/view.php?id=...`. Para a demonstração, use `POLL_SECONDS=10` para acompanhar os resultados sem esperar uma hora. O intervalo padrão é de 3600 segundos. O `.env` fica apenas na máquina local.

### 4. Rodar os serviços do projeto

```bash
docker compose up -d --build acompanhamento notificacoes
docker compose logs -f acompanhamento notificacoes
```

Abra o [Mailpit](http://localhost:8025) para conferir os e-mails. Para parar o ambiente preservando os volumes, use `docker compose down` sem `-v`. Para subir novamente, use `docker compose up -d`.

## Testes

Para executar a suíte automatizada:

```bash
python3 -m unittest discover -s tests -v
```

O [registro de testes](docs/testes.md) reúne os resultados dos cinco cenários executados no ambiente local: envio do lembrete, filtro de alunos e atividades, bloqueio de duplicatas, recuperação após falha no SMTP e persistência após recriar os contêineres. Os prints e os trechos dos logs estão no mesmo registro.
