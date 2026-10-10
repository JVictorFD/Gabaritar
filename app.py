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

# Importamos o PyZbar para leitura avançada de QR Codes minúsculos ou distantes
from pyzbar.pyzbar import decode

st.set_page_config(page_title="Gabaritar - Sistema OMR", page_icon="📝", layout="wide")

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
    st.write("Afaste um pouco o celular. A foto deve enquadrar tanto a caixa de Gabarito inteira quanto o QR Code.")
    
    if 'imagem_processada' not in st.session_state:
        st.session_state.imagem_processada = None
    if 'resultado_analise' not in st.session_state:
        st.session_state.resultado_analise = None
    if 'sucesso_salvamento' not in st.session_state:
        st.session_state.sucesso_salvamento = False
        
    foto_prova = st.file_uploader("📷 Tirar Foto (Usa a Câmera Nativa do Celular)", type=['png', 'jpg', 'jpeg'])
    
    if st.session_state.sucesso_salvamento:
        st.success("✨ Avaliação processada e salva com sucesso no banco de dados!")
        st.session_state.sucesso_salvamento = False
    
    if foto_prova is not None and st.session_state.imagem_processada != foto_prova.file_id:
        
        with st.status("Iniciando escaneamento da prova...", expanded=True) as status:
            st.write("🔄 Tratando formato e rotação da imagem do celular...")
            
            try:
                imagem_pil = Image.open(io.BytesIO(foto_prova.getvalue()))
                imagem_pil = ImageOps.exif_transpose(imagem_pil)
                
                array_pil = np.array(imagem_pil)
                if array_pil.shape[2] == 4: 
                    array_pil = cv2.cvtColor(array_pil, cv2.COLOR_RGBA2RGB)
                
                img_cv2_orig = cv2.cvtColor(array_pil, cv2.COLOR_RGB2BGR)
                st.write("📸 Foto carregada na memória com sucesso.")
            except Exception as e:
                status.update(label="Falha ao ler arquivo da câmera", state="error", expanded=True)
                st.error(f"❌ Erro ao decodificar a foto: {e}")
                st.stop()
            
            st.write("🔍 Extraindo informações do QR Code...")
            
            # --- NOVO: IMPLEMENTAÇÃO DO PYZBAR ---
            # PyZbar usa a imagem RGB/BGR pura, sem precisar de threshold cinza e agressivo, 
            # o que o torna infinitamente superior para ler QR Codes distantes ou pequenos.
            codigos_lidos = decode(img_cv2_orig)
            conteudo_qr = None
            
            if codigos_lidos:
                # Pega o conteúdo do primeiro código de barras/QR encontrado na foto
                conteudo_qr = codigos_lidos[0].data.decode("utf-8")
            
            prova_id_detectada = "DESCONHECIDO"
            gabarito_oficial = []
            
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
                st.error("❌ O sistema não encontrou o QR Code. Certifique-se de que a foto pegou a folha inteira e o código está nítido.")
                st.stop()
            
            st.write("⚙️ Analisando gabarito na imagem...")
            
            alt_orig, larg_orig = img_cv2_orig.shape[:2]
            nova_larg = 1000
            prop = nova_larg / float(larg_orig)
            nova_alt = int(alt_orig * prop)
            img_cv2 = cv2.resize(img_cv2_orig, (nova_larg, nova_alt))
            
            cinza = cv2.cvtColor(img_cv2, cv2.COLOR_BGR2GRAY)
            suavizada = cv2.GaussianBlur(cinza, (5, 5), 0)
            _, thresh = cv2.threshold(suavizada, 128, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)

            nota_calculada = 0.0
            respostas_lidas = []
            acertos = 0
            total_questoes = len(gabarito_oficial)
            
            if total_questoes > 0:
                contornos, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                bolinhas_validas = []
                
                for c in contornos:
                    (x, y, w, h) = cv2.boundingRect(c)
                    proporcao = w / float(h)
                    if 0.7 <= proporcao <= 1.3 and 15 <= w <= 60:
                        bolinhas_validas.append(c)
                
                bolinhas_esperadas = total_questoes * 5
                
                st.write(f"ℹ️ Encontradas {len(bolinhas_validas)} formas circulares (Esperado: {bolinhas_esperadas}).")
                
                if len(bolinhas_validas) >= bolinhas_esperadas:
                    st.write("📝 Processando marcações e calculando nota...")
                    
                    bolinhas_validas = sorted(bolinhas_validas, key=lambda b: cv2.boundingRect(b)[1])
                    
                    for i in range(0, min(len(bolinhas_validas), bolinhas_esperadas), 5):
                        linha = bolinhas_validas[i:i+5]
                        linha = sorted(linha, key=lambda b: cv2.boundingRect(b)[0])
                        
                        marcada = None
                        max_pixels = 0
                        area_media = 0
                        
                        for j, bolinha in enumerate(linha):
                            mask = np.zeros(thresh.shape, dtype="uint8")
                            cv2.drawContours(mask, [bolinha], -1, 255, -1)
                            mask = cv2.bitwise_and(thresh, thresh, mask=mask)
                            total_pixels = cv2.countNonZero(mask)
                            
                            if total_pixels > max_pixels:
                                max_pixels = total_pixels
                                marcada = j
                                _, _, bw, bh = cv2.boundingRect(bolinha)
                                area_media = bw * bh
                                
                        letras = ['A', 'B', 'C', 'D', 'E']
                        if marcada is not None and max_pixels > (area_media * 0.3):
                            respostas_lidas.append(letras[marcada])
                        else:
                            respostas_lidas.append("Nula/Branco")
                            
                    for lida, oficial in zip(respostas_lidas, gabarito_oficial):
                        if lida == oficial:
                            acertos += 1
                            
                    nota_calculada = (acertos / total_questoes) * 10.0
                    
                    st.session_state.resultado_analise = {
                        'prova_id': prova_id_detectada,
                        'gabarito_oficial': gabarito_oficial,
                        'respostas_lidas': respostas_lidas,
                        'nota': nota_calculada,
                        'acertos': acertos,
                        'total_questoes': total_questoes
                    }
                    st.session_state.imagem_processada = foto_prova.file_id
                    
                    status.update(label="Correção Óptica Finalizada!", state="complete", expanded=False)
                else:
                    status.update(label="Erro no enquadramento do gabarito", state="error", expanded=True)
                    st.error(f"❌ A câmera achou o QR Code perfeitamente, mas perdeu o Gabarito (Achou {len(bolinhas_validas)} de {bolinhas_esperadas} círculos). Tire uma foto sem cortar a caixa de gabarito à esquerda.")
            else:
                status.update(label="Nenhuma questão encontrada no QR Code", state="error", expanded=True)

    resultado = st.session_state.resultado_analise
    if resultado is not None and resultado['total_questoes'] > 0:
        
        st.markdown("---")
        st.subheader("🔍 Raio-X da Correção Automática")
        st.write(f"**ID da Prova:** `{resultado['prova_id']}`")
        
        df_resultado = pd.DataFrame({
            "Questão": [f"{i+1}" for i in range(resultado['total_questoes'])],
            "Gabarito Oficial": resultado['gabarito_oficial'],
            "Marcada pelo Aluno": resultado['respostas_lidas'],
            "Status": ["✅ Correta" if l == o else "❌ Errada" for l, o in zip(resultado['respostas_lidas'], resultado['gabarito_oficial'])]
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
                
                st.session_state.imagem_processada = None
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