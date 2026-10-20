<img src=".github/cover.png" width="100%" alt="ChatDeConversa: chat multi-protocolo em Python com multicast UDP, transferência de arquivos e IoT, com interface em Tkinter.">

# ChatDeConversa

Aplicação de chat multi-protocolo em Python, feita como projeto prático do curso de Ciências da Computação no IFSC.

O app principal é um chat em grupo sobre **UDP multicast** com interface em **Tkinter**: cada pessoa entra com um nome, no grupo `239.255.0.1`, porta `5000`, e as mensagens chegam para todo mundo da rede local. Os outros módulos exploram mais dois protocolos: **transferência de arquivos** cliente/servidor e um par cliente/servidor de **IoT** configurado por filial.

## Módulos

| Pasta | O que faz |
| :-- | :-- |
| `MainChat.py` | Ponto de entrada: chat multicast com interface Tkinter, threads para receber mensagens. |
| `chat/` | `ChatApp.py`, a lógica do chat. |
| `ftp/` | `FileServer.py` e `FileClient.py`, envio e recebimento de arquivos por socket. |
| `iot/` | `IoTServer.py` e `IoTClient.py`, com configurações por filial em JSON. |

## Tecnologias

- **Python** com a biblioteca padrão: `socket`, `threading`, `json`, `tkinter`
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
