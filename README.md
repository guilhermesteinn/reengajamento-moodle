# Reengajamento no Moodle

Trabalho de Engenharia de Software II — PUCRS, 2026/2.

Envia um lembrete por e-mail para quem ainda não entregou uma atividade que vence nas próximas 24 horas.

## Funcionamento

O projeto tem dois serviços:

- `acompanhamento`: consulta o Moodle pela API REST e publica as pendências no RabbitMQ.
- `notificacoes`: recebe as mensagens da fila e envia os e-mails por SMTP.

O e-mail contém o nome da atividade, o prazo no horário de Brasília e o link para acessá-la. Nos testes locais, os e-mails são recebidos pelo Mailpit.

Atividades vencidas, sem prazo ou que ainda não abriram são ignoradas. Alunos que já enviaram a tentativa atual não recebem lembrete. Entregas em rascunho continuam sendo consideradas pendentes.

Os envios são registrados no SQLite por curso, atividade e aluno. Pedidos repetidos são descartados depois do primeiro envio bem-sucedido.

Quando o SMTP falha, são feitas até três tentativas por mensagem, com intervalo de 15 segundos. Após a terceira falha, a mensagem vai para `lembretes.falhas`. As consultas seguintes podem gerar outro pedido enquanto a atividade continuar dentro dos critérios.

## Executar

É necessário ter Docker, Docker Compose v2 e conexão com a internet para montar as imagens.

### 1. Iniciar o ambiente

Na pasta do projeto:

```bash
cp -n .env.example .env
```

Defina `POSTGRES_PASSWORD` no `.env` antes da primeira instalação.

```bash
docker compose up -d --build moodle rabbitmq mailpit
```

### 2. Instalar o Moodle

Esta etapa é feita apenas na primeira instalação.

Copie a configuração:

```bash
docker compose exec -u www-data moodle cp /opt/moodle-config.php /var/moodle-state/config.php
docker compose exec -u root moodle cp --remove-destination /var/moodle-state/config.php /var/www/html/config.php
```

No Bash, execute o instalador:

```bash
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

Acesse http://localhost:8080 e entre com o usuário `admin` e a senha definida.

Crie um curso, matricule dois alunos fictícios e adicione uma atividade com prazo para aproximadamente duas horas à frente. Faça a entrega com um dos alunos e deixe o outro sem entregar.

### 3. Configurar a integração

Na administração do Moodle:

1. Habilite **Enable web services** em **Advanced features**.
2. Ative **REST** em **Server → Web services → Manage protocols**.
3. Crie um serviço externo habilitado, restrito a usuários autorizados.
4. Adicione as funções:

```text
mod_assign_get_assignments
core_enrol_get_enrolled_users
mod_assign_get_submissions
```

Crie um usuário para a integração e matricule-o como professor no curso. Conceda a permissão `webservice/rest:use`, autorize esse usuário no serviço externo e gere um token em **Manage tokens**.

A consulta dos alunos precisa retornar os campos `roles` e `email`.

Preencha no `.env`:

- `MOODLE_TOKEN`: token gerado no Moodle.
- `MOODLE_COURSE_ID`: ID do curso, disponível na URL `course/view.php?id=...`.
- `POLL_SECONDS`: intervalo entre consultas, em segundos. O padrão é `3600`; para testar, use `10`.

O `.env` não deve ser enviado ao repositório.

### 4. Iniciar os serviços

```bash
docker compose up -d --build acompanhamento notificacoes
```

Para acompanhar os logs:

```bash
docker compose logs -f acompanhamento notificacoes
```

Para consultar os e-mails, abra http://localhost:8025.

### Parar e iniciar novamente

Para parar preservando os dados:

```bash
docker compose down
```

Para iniciar novamente:

```bash
docker compose up -d
```

Não use `docker compose down -v` se quiser manter os volumes.

## Testes

Execute:

```bash
python3 -m unittest discover -s tests -v
```

Os testes automatizados usam respostas simuladas do Moodle e do SMTP.

Os testes de integração foram feitos com Moodle, RabbitMQ e Mailpit em Docker. Foram verificados:

- Envio para o aluno com atividade pendente.
- Filtro de alunos que já entregaram e de atividades fora dos critérios.
- Descarte de mensagens duplicadas.
- Nova tentativa após falha no SMTP.
- Persistência dos dados após recriar os contêineres.

Os resultados, prints e logs estão em [docs/testes.md](docs/testes.md).

## Limitações

Os testes foram feitos com atividades individuais, visíveis para toda a turma.

Se o serviço parar depois de enviar o e-mail e antes de registrar o envio no SQLite, o lembrete pode ser enviado novamente.
