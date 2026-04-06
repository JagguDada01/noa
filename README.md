# Noa

Noa is a terminal-based AI assistant powered by a local Ollama model.

It runs on your own machine, works without a browser, and can keep working with Wi-Fi off after the model is already downloaded.

## Features

- terminal chat interface
- local Ollama model support
- streaming responses
- automatic local model detection
- automatic `ollama serve` startup
- simple commands for switching models and clearing chat history

## Requirements

- Python 3.10 or newer
- [Ollama](https://ollama.com/) installed
- at least one Ollama model downloaded locally

## Quick Start

### 1. Clone the project

```bash
git clone https://github.com/YOUR_USERNAME/noa.git
cd noa
```

### 2. Install Ollama

Install Ollama for your system, then make sure this works:

```bash
ollama --version
```

### 3. Download a model

Example:

```bash
ollama pull llama3.2:3b
```

You only need internet for this step the first time.

### 4. Start Noa

```bash
chmod +x noa offline_chat.py
./noa
```

## Run Commands

Start interactive chat:

```bash
./noa
```

List local models:

```bash
./noa --list-models
```

Use a specific model:

```bash
./noa --model llama3.2:3b
```

Ask one question and exit:

```bash
./noa --once "Explain recursion simply."
```

Do not auto-start the Ollama server:

```bash
./noa --no-auto-start
```

Run the Python file directly:

```bash
python3 offline_chat.py
```

## Optional Global Command

If you want to run Noa as `noa` from anywhere:

```bash
chmod +x noa offline_chat.py
sudo ln -sf "$(pwd)/noa" /usr/local/bin/noa
```

Then use:

```bash
noa
```

On Apple Silicon systems using Homebrew, you can also use:

```bash
sudo ln -sf "$(pwd)/noa" /opt/homebrew/bin/noa
```

## Chat Commands

- `/help`
- `/models`
- `/model NAME`
- `/clear`
- `/system TEXT`
- `/status`
- `/exit`

## Offline Use

Noa works offline after:

- Ollama is installed
- a model is already downloaded locally

If the model is not present yet, download it first:

```bash
ollama pull llama3.2:3b
```

## Project Files

- `offline_chat.py` - main terminal chatbot
- `noa` - launcher script

## Example

```bash
./noa --model llama3.2:3b
```

## License

MIT License. See `LICENSE`.
