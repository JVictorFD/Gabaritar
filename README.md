# 📝 Gabaritar

**Gabaritar** é uma aplicação web interativa desenvolvida em Python para professores e instituições de ensino. O sistema automatiza a criação, distribuição e correção de provas utilizando geração dinâmica de PDFs com QR Codes únicos e leitura de gabaritos por Visão Computacional (OMR - *Optical Mark Recognition*).

---

## ⚙️ Funcionalidades Atuais (v1.0.0)

Nesta primeira fase de protótipo, o sistema foca na **Geração do Lote de Provas**:
*   **Criação Dinâmica de Questões:** Cadastre questões de Múltipla Escolha e Textuais (Discursivas) diretamente pela interface intuitiva.
*   **Geração em Lote (PDF):** Defina a quantidade de provas que deseja gerar (ex: 50 provas) e o sistema consolidará todas em um único arquivo PDF pronto para impressão.
*   **Injeção de QR Code Único:** Cada página do PDF gerado recebe um ID exclusivo e um QR Code para rastreamento individual do aluno na hora da correção.
*   **Bubble Sheet (Gabarito) Automático:** Se houver questões de múltipla escolha, o sistema desenha perfeitamente a grade de bolinhas de resposta no cabeçalho da prova, otimizada para a futura leitura por câmera de celular.

---

## 🚀 Como rodar localmente

Este passo a passo foi desenhado para ser simples e direto, permitindo que qualquer pessoa consiga rodar a interface de criação de provas no próprio computador.

### Pré-requisitos
Você precisa ter o **Python** instalado. Se não tiver, baixe a versão mais recente em [python.org](https://www.python.org/).

### Passo a Passo

1. **Abra o terminal na pasta do projeto**
   Crie uma pasta para o projeto, salve os arquivos nela e abra no VS Code. Abra o terminal integrado (`Ctrl` + `'`).

2. **Crie um ambiente virtual (Recomendado)**
   Isso cria uma "bolha" segura para instalar as bibliotecas sem afetar o resto do seu computador. No terminal, digite:
   * **No Windows:**
     ```bash
     python -m venv venv
     .\venv\Scripts\activate
     ```
   * **No Mac / Linux:**
     ```bash
     python3 -m venv venv
     source venv/bin/activate
     ```

3. **Instale as dependências**
   Com o ambiente ativado (você verá `(venv)` no terminal), instale as bibliotecas necessárias para a geração do PDF e da interface:
   ```bash
   pip install -r requirements.txt