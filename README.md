<img src=".github/cover.png" width="100%" alt="ChatDeConversa: chat multi-protocolo em Python com multicast UDP, transferência de arquivos e IoT, com interface em Tkinter.">

# ChatDeConversa

Aplicação de chat multi-protocolo em Python, feita como projeto prático do curso de Ciências da Computação no IFSC.

O app principal é um chat em grupo sobre **UDP multicast** com interface no **estilo WhatsApp**, feita em **Tkinter**: tela de entrada com nome, grupo e porta, e uma conversa com balões, nome colorido de cada pessoa, horário e os dois checks azuis quando a sua mensagem chega no grupo. Não tem servidor: cada mensagem vai direto para todo mundo da rede local que entrou no mesmo grupo (padrão `239.255.0.1`, porta `5000`). Os outros módulos exploram mais dois protocolos: **transferência de arquivos** cliente/servidor e um par cliente/servidor de **IoT** configurado por filial.

<p align="center">
  <img src="docs/login.png" width="38%" alt="Tela de entrada do ChatDeConversa: nome, grupo multicast e porta, com botão verde Entrar no grupo.">
  &nbsp;
  <img src="docs/chat.png" width="38%" alt="Conversa em grupo no estilo WhatsApp: balões cinza de outras pessoas com nome colorido, balões verdes enviados com horário e dois checks azuis.">
</p>

### Como funciona a interface

- **Balões** desenhados num `Canvas`, com cantos arredondados e a pontinha do lado de quem enviou.
- **Dois checks azuis**: cada mensagem leva um `id`; quando o eco do multicast volta para quem enviou, o ✓ vira ✓✓.
- **Thread-safe**: a thread de rede só coloca o que chega numa `queue.Queue`; a interface lê a fila com `after()`, sem tocar no Tkinter fora da thread principal.
- **Compatível** com o formato antigo de mensagem (`date`, `time`, `username`, `message`): os campos novos (`id`, `client`) são opcionais.
- **Nítido em telas com escala** (Windows com 125% ou 150%).

## Módulos

| Pasta | O que faz |
| :-- | :-- |
| `MainChat.py` | Ponto de entrada: abre o chat. |
| `chat/` | `ChatApp.py`: interface estilo WhatsApp e a rede multicast (envio, recepção em thread, confirmação de entrega). |
| `ftp/` | `FileServer.py` e `FileClient.py`, envio e recebimento de arquivos por socket. |
| `iot/` | `IoTServer.py` e `IoTClient.py`, com configurações por filial em JSON. |

## Tecnologias

- **Python** só com a biblioteca padrão: `socket`, `threading`, `queue`, `json`, `tkinter`
- **UDP multicast** para o chat em grupo
- **TCP** para a transferência de arquivos e **UDP** para o módulo IoT

## Como executar

```bash
git clone https://github.com/KaioHomem/ChatDeConversa.git
cd ChatDeConversa
python MainChat.py
```

Abra em duas máquinas (ou dois terminais) na mesma rede, conecte no mesmo grupo e porta, e converse.

## Autor

**Kaio Felipe Homem** · [Portfólio](https://kaiohomem.github.io) · [GitHub](https://github.com/KaioHomem)

<sub>Projeto acadêmico · IFSC · Ciências da Computação</sub>
