import streamlit as st
import tempfile
import os
import uuid
import qrcode
from fpdf import FPDF
import cv2
import numpy as np
import sqlite3
import pandas as pd
import time
from PIL import Image, ImageOps
import io

from pyzbar.pyzbar import decode

st.set_page_config(page_title="Gabaritar - Sistema OMR", page_icon="📝", layout="wide")

# --- FUNÇÃO MATEMÁTICA PARA CORREÇÃO DE PERSPECTIVA ---
def ordenar_pontos(pontos):
    pontos = pontos.reshape((4, 2))
    nova_ordem = np.zeros((4, 2), dtype=np.float32)
    soma = pontos.sum(axis=1)
    nova_ordem[0] = pontos[np.argmin(soma)]
    nova_ordem[2] = pontos[np.argmax(soma)]
    diff = np.diff(pontos, axis=1)
    nova_ordem[1] = pontos[np.argmin(diff)]
    nova_ordem[3] = pontos[np.argmax(diff)]
    return nova_ordem

# --- BANCO DE DADOS LOCAL ---
def inicializar_banco():
    conn = sqlite3.connect('notas_alunos.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS correcoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prova_id TEXT,
            nome_aluno TEXT,
            matricula TEXT,
            nota REAL,
            data_hora TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

inicializar_banco()

# --- FUNÇÕES GERADORAS DE PDF (MÓDULO 1) ---
def higienizar_texto(texto):
    return str(texto).encode('latin-1', 'replace').decode('latin-1')

def gerar_pdf(titulo, questoes, quantidade):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    multiplas = [q for q in questoes if q['tipo'] == 'Múltipla Escolha']
    string_gabarito = ""
    if multiplas:
        lista_respostas = []
        for idx, q in enumerate(multiplas):
            lista_respostas.append(f"Q{idx+1}-{q['correta']}")
        string_gabarito = "; ".join(lista_respostas)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        for i in range(quantidade):
            pdf.add_page()
            prova_id = str(uuid.uuid4())[:8].upper()
            
            dados_qr = f"{prova_id}|{string_gabarito}" if string_gabarito else prova_id
            
            qr_path = os.path.join(tmpdir, f"qr_{i}.png")
            qr = qrcode.QRCode(version=1, box_size=5, border=1)
            qr.add_data(dados_qr)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            img.save(qr_path)
            
            pdf.set_font("Arial", "B", 16)
            pdf.cell(0, 10, higienizar_texto(titulo), ln=1, align="C")
            pdf.ln(2)
            
            y_ancora = pdf.get_y()
            
            pdf.set_font("Arial", "", 11)
            pdf.set_xy(10, y_ancora)
            pdf.cell(90, 7, higienizar_texto("Nome: ______________________________________"), ln=1)
            pdf.cell(90, 7, higienizar_texto("Matrícula: _________________   Turma: _________"), ln=1)
            
            pdf.set_font("Arial", "B", 10)
            pdf.cell(90, 7, higienizar_texto(f"ID Exclusivo da Prova: {prova_id}"), ln=1)
            y_fim_aluno = pdf.get_y()
            
            y_fim_gabarito = y_ancora
            
            if multiplas:
                altura_gab = 10 + (6 * len(multiplas))
                pdf.rect(105, y_ancora, 65, altura_gab) 
                
                pdf.set_xy(105, y_ancora + 1)
                pdf.set_font("Arial", "B", 9)
                pdf.cell(65, 5, higienizar_texto("GABARITO"), ln=1, align="C")
                
                y_gab = y_ancora + 8
                
                for idx_q, q in enumerate(multiplas):
                    pdf.set_font("Arial", "", 8)
                    pdf.set_xy(107, y_gab)
                    pdf.cell(6, 5, f"{idx_q+1}.", ln=0)
                    
                    letras = ['A', 'B', 'C', 'D', 'E']
                    for alt in letras:
                        pdf.set_font("Arial", "", 10)
                        pdf.cell(10, 5, "O", ln=0)
                    y_gab += 6
                
                y_fim_gabarito = y_ancora + altura_gab
            
            pdf.image(qr_path, x=175, y=y_ancora, w=25)
            y_fim_qr = y_ancora + 25
            
            pos_y_linha = max(y_fim_aluno, y_fim_gabarito, y_fim_qr) + 5
            pdf.set_y(pos_y_linha)
            pdf.line(10, pdf.get_y(), 200, pdf.get_y())
            pdf.ln(5)
            
            for idx_q, q in enumerate(questoes):
                pdf.set_font("Arial", "B", 11)
                pdf.multi_cell(0, 6, higienizar_texto(f"Questão {idx_q+1}: {q['enunciado']}"))
                pdf.set_font("Arial", "", 11)
                
                if q['tipo'] == 'Múltipla Escolha':
                    letras = ['A', 'B', 'C', 'D', 'E']
                    for idx_opt, opt in enumerate(q['opcoes']):
                        if opt.strip():
                            pdf.multi_cell(0, 6, higienizar_texto(f" {letras[idx_opt]}) {opt}"))
                else:
                    pdf.cell(0, 25, "", ln=1) 
                
                pdf.ln(4)
                
        pdf_path = os.path.join(tmpdir, "provas_geradas.pdf")
        pdf.output(pdf_path)
        
        with open(pdf_path, "rb") as f:
            return f.read()

# --- INTERFACE DO STREAMLIT ---
st.title("📝 Gabaritar")

aba_gerar, aba_corrigir, aba_relatorio = st.tabs(["1️⃣ Gerar Provas", "2️⃣ Escanear e Corrigir", "3️⃣ Relatórios"])

# ==========================================
# ABA 1: GERADOR DE PROVAS
# ==========================================
with aba_gerar:
    st.write("Cadastre as questões, defina o gabarito e gere o lote em PDF.")

    if 'questoes' not in st.session_state:
        st.session_state.questoes = []

    col_config, col_add = st.columns([1, 2])
    
    with col_config:
        st.header("⚙️ Lote")
        titulo_prova = st.text_input("Título da Avaliação", "Prova Bimestral")
        qtd_provas = st.number_input("Quantidade de Provas", min_value=1, max_value=500, value=1)
        st.info(f"📊 Questões cadastradas: **{len(st.session_state.questoes)}**")

    with col_add:
        st.subheader("Adicionar Questão")
        tipo_questao = st.radio("Tipo:", ["Múltipla Escolha", "Textual"], horizontal=True)
        enunciado = st.text_area("Enunciado", placeholder="Digite a pergunta...")

        opcoes = ["", "", "", "", ""]
        correta = ""
        
        if tipo_questao == "Múltipla Escolha":
            c1, c2 = st.columns(2)
            with c1:
                opcoes[0] = st.text_input("Opção A")
                opcoes[2] = st.text_input("Opção C")
                opcoes[4] = st.text_input("Opção E")
            with c2:
                opcoes[1] = st.text_input("Opção B")
                opcoes[3] = st.text_input("Opção D")
                
            correta = st.selectbox("🎯 Alternativa Correta:", ["A", "B", "C", "D", "E"])

        if st.button("➕ Adicionar Questão"):
            if enunciado.strip():
                nova_questao = {
                    "enunciado": enunciado, 
                    "tipo": tipo_questao, 
                    "opcoes": opcoes if tipo_questao == "Múltipla Escolha" else [],
                    "correta": correta
                }
                st.session_state.questoes.append(nova_questao)
                st.success("Questão adicionada!")
                st.rerun()

    if st.button("🚀 Gerar Lote em PDF", type="primary", use_container_width=True):
        if len(st.session_state.questoes) > 0:
            with st.spinner("Embutindo chaves no QR Code e gerando PDF..."):
                pdf_bytes = gerar_pdf(titulo_prova, st.session_state.questoes, qtd_provas)
                st.success("Lote gerado com sucesso!")
                st.download_button("📥 Baixar PDF Pronto para Impressão", data=pdf_bytes, file_name="Provas.pdf", mime="application/pdf")

# ==========================================
# ABA 2: MÓDULO DE ESCANEAMENTO (OMR INTELIGENTE)
# ==========================================
with aba_corrigir:
    st.write("Afaste um pouco a câmera ou envie um print contendo o Gabarito e o QR Code.")
    
    if 'imagem_processada' not in st.session_state:
        st.session_state.imagem_processada = None
    if 'resultado_analise' not in st.session_state:
        st.session_state.resultado_analise = None
    if 'sucesso_salvamento' not in st.session_state:
        st.session_state.sucesso_salvamento = False
        
    foto_prova = st.file_uploader("📷 Enviar Foto ou Print", type=['png', 'jpg', 'jpeg'])
    
    if st.session_state.sucesso_salvamento:
        st.success("✨ Avaliação salva com sucesso no banco de dados!")
        st.session_state.sucesso_salvamento = False
    
    if foto_prova is not None and st.session_state.imagem_processada != foto_prova.file_id:
        
        st.session_state.imagem_processada = foto_prova.file_id
        st.session_state.resultado_analise = None
        
        with st.status("Iniciando escaneamento da prova...", expanded=True) as status:
            passo_sucesso = True
            st.write("🔄 Tratando formato da imagem...")
            
            try:
                imagem_pil = Image.open(io.BytesIO(foto_prova.getvalue()))
                imagem_pil = ImageOps.exif_transpose(imagem_pil)
                array_pil = np.array(imagem_pil)
                if array_pil.shape[2] == 4: 
                    array_pil = cv2.cvtColor(array_pil, cv2.COLOR_RGBA2RGB)
                img_cv2_orig = cv2.cvtColor(array_pil, cv2.COLOR_RGB2BGR)
                st.write("📸 Imagem carregada na memória com sucesso.")
            except Exception as e:
                status.update(label="Falha ao decodificar a foto", state="error", expanded=True)
                st.error(f"❌ Erro ao decodificar a foto: {e}")
                passo_sucesso = False
            
            prova_id_detectada = "DESCONHECIDO"
            gabarito_oficial = []
            qr_rect = None
            
            if passo_sucesso:
                st.write("🔍 Extraindo informações do QR Code...")
                codigos_lidos = decode(img_cv2_orig)
                conteudo_qr = None
                
                if codigos_lidos:
                    codigo = codigos_lidos[0]
                    conteudo_qr = codigo.data.decode("utf-8")
                    qr_rect = codigo.rect
                
                if conteudo_qr:
                    if "|" in conteudo_qr:
                        prova_id_detectada, string_gabarito = conteudo_qr.split("|")
                        partes = string_gabarito.split(";")
                        for p in partes:
                            if "-" in p:
                                _, resposta = p.split("-")
                                gabarito_oficial.append(resposta.strip())
                        st.write(f"✅ Respostas extraídas: A chave do ID **{prova_id_detectada}** foi carregada.")
                    else:
                        prova_id_detectada = conteudo_qr
                        st.write(f"⚠️ Atenção: QR lido ({prova_id_detectada}), mas sem gabarito atrelado.")
                else:
                    status.update(label="Falha na leitura do QR Code", state="error", expanded=True)
                    st.error("❌ O sistema não encontrou o QR Code. Certifique-se de que a imagem contém o código nítido.")
                    passo_sucesso = False
            
            if passo_sucesso and gabarito_oficial:
                st.write("📐 Alinhando grade matemática do Gabarito...")
                cinza = cv2.cvtColor(img_cv2_orig, cv2.COLOR_BGR2GRAY)
                suavizada = cv2.GaussianBlur(cinza, (5, 5), 0)
                _, thresh = cv2.threshold(suavizada, 128, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)

                N_questoes = len(gabarito_oficial)
                target_w = 650
                target_h = 100 + 60 * N_questoes
                
                # --- NOVO: FECHAMENTO MORFOLÓGICO PARA PRINTS INCOMPLETOS ---
                # A imagem do usuário pode ter cortado a borda de baixo. O Dilate conecta as linhas pretas grossas.
                kernel = np.ones((7, 7), np.uint8)
                borda_forte = cv2.dilate(thresh, kernel, iterations=2)
                contornos, _ = cv2.findContours(borda_forte, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                
                target_ratio = 65.0 / (10 + 6 * N_questoes)
                melhor_contorno = None
                menor_erro = 1000
                
                for c in contornos:
                    perimetro = cv2.arcLength(c, True)
                    aproximacao = cv2.approxPolyDP(c, 0.04 * perimetro, True)
                    if len(aproximacao) == 4:
                        x, y, w, h = cv2.boundingRect(aproximacao)
                        if w > 50 and h > 50 and (x + w/2 < qr_rect.left + qr_rect.width):
                            ratio = w / float(h)
                            erro = abs(ratio - target_ratio) / target_ratio
                            if erro < 0.35: # Tolerância aumentada para prints mal recortados
                                if erro < menor_erro:
                                    menor_erro = erro
                                    melhor_contorno = aproximacao
                
                gabarito_warped = None
                if melhor_contorno is not None:
                    st.write("✅ Caixa preta do gabarito detectada. Corrigindo perspectiva...")
                    pontos_doc = ordenar_pontos(melhor_contorno)
                    pontos_destino = np.array([[0, 0], [target_w - 1, 0], [target_w - 1, target_h - 1], [0, target_h - 1]], dtype="float32")
                    matriz = cv2.getPerspectiveTransform(pontos_doc, pontos_destino)
                    gabarito_warped = cv2.warpPerspective(thresh, matriz, (target_w, target_h))
                else:
                    st.write("⚠️ Contorno da caixa corrompido ou cortado. Aplicando inferência geométrica rígida pelo QR Code...")
                    K = qr_rect.width / 25.0
                    gab_x = max(0, int(qr_rect.left - 70 * K))
                    gab_y = max(0, int(qr_rect.top))
                    gab_w = int(65 * K)
                    gab_h = int((10 + 6 * N_questoes) * K)
                    
                    gabarito_crop = thresh[gab_y:gab_y+gab_h, gab_x:gab_x+gab_w]
                    if gabarito_crop.size > 0:
                        gabarito_warped = cv2.resize(gabarito_crop, (target_w, target_h))
                    else:
                        status.update(label="Erro crítico no recorte", state="error", expanded=True)
                        st.error("❌ Não foi possível extrair a área do gabarito matematicamente.")
                        passo_sucesso = False
                        
                if passo_sucesso and gabarito_warped is not None:
                    st.write("📝 Avaliando contraste estatístico da tinta para ignorar bolinhas vazias...")
                    
                    respostas_lidas = []
                    acertos = 0
                    letras = ['A', 'B', 'C', 'D', 'E']
                    
                    for i in range(N_questoes):
                        y_centro = 105 + i * 60
                        densidades = []
                        
                        for j in range(5):
                            x_centro = 130 + j * 100
                            cell_roi = gabarito_warped[max(0, y_centro - 15) : y_centro + 15, max(0, x_centro - 25) : x_centro + 25]
                            
                            if cell_roi.size > 0:
                                pixels_brancos = cv2.countNonZero(cell_roi) 
                                densidades.append(pixels_brancos)
                            else:
                                densidades.append(0)
                        
                        # --- NOVO: LÓGICA ESTATÍSTICA COMPARATIVA (Z-Score rudimentar) ---
                        # Em vez de um limite percentual fixo que falha em fotos escuras, o sistema
                        # olha para a média de tinta das 5 opções. 
                        # Uma opção só é validada como "marcada" se ela tiver MUITO MAIS TINTA (pelo menos 50% mais escura)
                        # do que a média daquela mesma linha. Se todas forem similares (ex: todas vazias), é Em Branco.
                        media_linha = np.mean(densidades)
                        max_densidade = max(densidades)
                        
                        # A margem segura: A opção mais pintada tem que ser 1.5x mais preta que a média da linha inteira
                        if max_densidade > (media_linha * 1.5) and max_densidade > 100: 
                            idx_marcada = densidades.index(max_densidade)
                            respostas_lidas.append(letras[idx_marcada])
                        else:
                            respostas_lidas.append("Em Branco")
                            
                    for lida, oficial in zip(respostas_lidas, gabarito_oficial):
                        if lida == oficial:
                            acertos += 1
                            
                    nota_calculada = (acertos / N_questoes) * 10.0
                    
                    st.session_state.resultado_analise = {
                        'prova_id': prova_id_detectada,
                        'gabarito_oficial': gabarito_oficial,
                        'respostas_lidas': respostas_lidas,
                        'nota': nota_calculada,
                        'acertos': acertos,
                        'total_questoes': N_questoes
                    }
                    status.update(label="Correção Óptica Finalizada!", state="complete", expanded=False)

    # Renderiza o painel cruzado
    resultado = st.session_state.resultado_analise
    if resultado is not None and resultado['total_questoes'] > 0:
        
        st.markdown("---")
        st.subheader("🔍 Raio-X da Correção Automática")
        st.write(f"**ID da Prova:** `{resultado['prova_id']}`")
        
        df_resultado = pd.DataFrame({
            "Questão": [f"{i+1}" for i in range(resultado['total_questoes'])],
            "Gabarito Oficial": resultado['gabarito_oficial'],
            "Marcada pelo Aluno": resultado['respostas_lidas'],
            "Status": ["✅ Correta" if l == o else ("⚪ Não Respondida" if l == "Em Branco" else "❌ Errada") for l, o in zip(resultado['respostas_lidas'], resultado['gabarito_oficial'])]
        })
        
        st.dataframe(df_resultado, use_container_width=True, hide_index=True)
        
        st.markdown("---")
        st.subheader("🎓 Inserir Boletim do Aluno")
        col_n, col_m, col_v = st.columns([2, 1, 1])
        
        nome_aluno = col_n.text_input("Nome do Aluno")
        matricula_aluno = col_m.text_input("Matrícula")
        col_v.metric(label="Nota Calculada", value=f"{resultado['nota']:.1f}", delta=f"{resultado['acertos']} Acertos", delta_color="normal")
        
        if st.button("Salvar no Banco de Dados 💾", type="primary"):
            if nome_aluno:
                conn = sqlite3.connect('notas_alunos.db')
                c = conn.cursor()
                c.execute("INSERT INTO correcoes (prova_id, nome_aluno, matricula, nota) VALUES (?, ?, ?, ?)", 
                          (resultado['prova_id'], nome_aluno, matricula_aluno, resultado['nota']))
                conn.commit()
                conn.close()
                
                st.session_state.resultado_analise = None
                st.session_state.sucesso_salvamento = True
                st.rerun()
            else:
                st.error("Digite o nome do aluno antes de salvar.")

# ==========================================
# ABA 3: RELATÓRIOS E EXPORTAÇÃO
# ==========================================
with aba_relatorio:
    st.write("Acompanhe o andamento das correções desta sessão.")
    
    if st.button("🔄 Atualizar Relatório"):
        pass 
        
    conn = sqlite3.connect('notas_alunos.db')
    df_notas = pd.read_sql_query("SELECT id, prova_id as ID_Prova, nome_aluno as Nome, matricula as Matrícula, nota as Nota, data_hora as Data FROM correcoes", conn)
    conn.close()
    
    if not df_notas.empty:
        st.dataframe(df_notas, use_container_width=True, hide_index=True)
        
        csv = df_notas.to_csv(index=False)
        st.download_button(
            label="📥 Finalizar Sessão e Exportar Relatório (CSV)",
            data=csv,
            file_name="Relatorio_Notas_Gabaritar.csv",
            mime="text/csv",
            type="primary"
        )
    else:
        st.info("Nenhuma prova foi corrigida ainda no banco de dados.")