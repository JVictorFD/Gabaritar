import streamlit as st
import tempfile
import os
import uuid
import qrcode
from fpdf import FPDF
import cv2
import numpy as np
import sqlite3
import json

st.set_page_config(page_title="Gabaritar - Sistema OMR", page_icon="📝", layout="wide")

# --- BANCO DE DADOS LOCAL ---
def inicializar_banco():
    """Cria tabelas para salvar as correções e os gabaritos oficiais gerados."""
    conn = sqlite3.connect('notas_alunos.db')
    cursor = conn.cursor()
    
    # Tabela do histórico de alunos e notas
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
    
    # Tabela para guardar as respostas corretas vinculadas a cada QR Code
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS gabaritos (
            prova_id TEXT PRIMARY KEY,
            respostas TEXT
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
    
    # Extrai o gabarito oficial das questões configuradas pelo professor
    respostas_oficiais = [q['correta'] for q in questoes if q['tipo'] == 'Múltipla Escolha']
    
    with tempfile.TemporaryDirectory() as tmpdir:
        for i in range(quantidade):
            pdf.add_page()
            prova_id = str(uuid.uuid4())[:8].upper()
            
            # Salva o gabarito oficial deste ID específico no Banco de Dados
            conn = sqlite3.connect('notas_alunos.db')
            c = conn.cursor()
            c.execute("INSERT OR REPLACE INTO gabaritos (prova_id, respostas) VALUES (?, ?)", 
                      (prova_id, json.dumps(respostas_oficiais)))
            conn.commit()
            conn.close()
            
            qr_path = os.path.join(tmpdir, f"qr_{i}.png")
            qr = qrcode.QRCode(version=1, box_size=5, border=1)
            qr.add_data(prova_id)
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
            
            multiplas = [q for q in questoes if q['tipo'] == 'Múltipla Escolha']
            y_fim_gabarito = y_ancora
            
            if multiplas:
                altura_gab = 10 + (5 * len(multiplas))
                pdf.rect(105, y_ancora, 60, altura_gab) 
                
                pdf.set_xy(105, y_ancora + 1)
                pdf.set_font("Arial", "B", 9)
                pdf.cell(60, 5, higienizar_texto("GABARITO"), ln=1, align="C")
                
                y_gab = y_ancora + 8
                pdf.set_font("Arial", "", 8)
                
                for idx_q, q in enumerate(questoes):
                    if q['tipo'] == 'Múltipla Escolha':
                        pdf.set_xy(107, y_gab)
                        pdf.cell(6, 4, f"{idx_q+1}.", ln=0)
                        for alt in ['A', 'B', 'C', 'D', 'E']:
                            pdf.cell(9, 4, f"({alt})", ln=0)
                        y_gab += 5
                
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
            with st.spinner("Vinculando gabaritos no Banco de Dados e gerando PDF..."):
                pdf_bytes = gerar_pdf(titulo_prova, st.session_state.questoes, qtd_provas)
                st.success("Lote gerado com sucesso!")
                st.download_button("📥 Baixar PDF Pronto para Impressão", data=pdf_bytes, file_name="Provas.pdf", mime="application/pdf")

# ==========================================
# ABA 2: MÓDULO DE ESCANEAMENTO (OMR INTELIGENTE)
# ==========================================
with aba_corrigir:
    st.write("Tire uma foto nítida e bem iluminada do cabeçalho da prova.")
    
    foto_prova = st.camera_input("📷 Escanear Folha")
    
    if foto_prova is not None:
        bytes_data = foto_prova.getvalue()
        array_np = np.frombuffer(bytes_data, np.uint8)
        img_cv2 = cv2.imdecode(array_np, cv2.IMREAD_COLOR)
        
        cinza = cv2.cvtColor(img_cv2, cv2.COLOR_BGR2GRAY)
        suavizada = cv2.GaussianBlur(cinza, (5, 5), 0)
        _, thresh = cv2.threshold(suavizada, 128, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
        
        detector_qr = cv2.QRCodeDetector()
        prova_id, _, _ = detector_qr.detectAndDecode(cinza)
        
        if prova_id:
            st.success(f"✅ QR Code Detectado! ID: **{prova_id}**")
            
            # 1. Recuperar o Gabarito Oficial do Banco de Dados
            conn = sqlite3.connect('notas_alunos.db')
            c = conn.cursor()
            c.execute("SELECT respostas FROM gabaritos WHERE prova_id = ?", (prova_id,))
            resultado_bd = c.fetchone()
            conn.close()
            
            nota_calculada = 0.0
            
            if resultado_bd:
                gabarito_oficial = json.loads(resultado_bd[0])
                total_questoes = len(gabarito_oficial)
                
                # 2. Filtrar os contornos que têm formato de bolinha
                contornos, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                bolinhas_validas = []
                
                for c in contornos:
                    (x, y, w, h) = cv2.boundingRect(c)
                    proporcao = w / float(h)
                    if 0.8 <= proporcao <= 1.2 and 10 <= w <= 60:
                        bolinhas_validas.append(c)
                
                # A máquina precisa enxergar exatamente a matriz completa (Questões x 5 opções)
                bolinhas_esperadas = total_questoes * 5
                
                if len(bolinhas_validas) == bolinhas_esperadas and total_questoes > 0:
                    # Ordena todas as bolinhas de cima para baixo (eixo Y)
                    bolinhas_validas = sorted(bolinhas_validas, key=lambda b: cv2.boundingRect(b)[1])
                    
                    respostas_lidas = []
                    acertos = 0
                    
                    # Agrupa as bolinhas em linhas (5 opções por questão)
                    for i in range(0, len(bolinhas_validas), 5):
                        linha = bolinhas_validas[i:i+5]
                        # Ordena a linha da esquerda para a direita (eixo X)
                        linha = sorted(linha, key=lambda b: cv2.boundingRect(b)[0])
                        
                        marcada = None
                        max_pixels = 0
                        
                        # Verifica qual bolinha tem mais tinta escura (pixels brancos na máscara invertida)
                        for j, bolinha in enumerate(linha):
                            mask = np.zeros(thresh.shape, dtype="uint8")
                            cv2.drawContours(mask, [bolinha], -1, 255, -1)
                            mask = cv2.bitwise_and(thresh, thresh, mask=mask)
                            total_pixels = cv2.countNonZero(mask)
                            
                            if total_pixels > max_pixels:
                                max_pixels = total_pixels
                                marcada = j
                                
                        letras = ['A', 'B', 'C', 'D', 'E']
                        if marcada is not None:
                            respostas_lidas.append(letras[marcada])
                            
                    # 3. Comparação Final e Cálculo da Nota
                    for lida, oficial in zip(respostas_lidas, gabarito_oficial):
                        if lida == oficial:
                            acertos += 1
                            
                    nota_calculada = (acertos / total_questoes) * 10.0
                    st.info(f"🎯 **Análise Concluída:** {acertos} acertos de {total_questoes} questões.")
                else:
                    st.warning(f"⚠️ A câmera detectou {len(bolinhas_validas)} marcações redondas, mas eram esperadas {bolinhas_esperadas}. Aproxime o celular para focar apenas no quadro do gabarito sem sombras fortes.")
            else:
                st.error("❌ Gabarito não encontrado para este ID. Certifique-se de que a prova foi gerada neste dispositivo.")
            
            # Painel de Inserção de Dados
            with st.form("form_salvar_nota", clear_on_submit=True):
                st.subheader("Registrar no Sistema")
                col_n, col_m, col_v = st.columns([2, 1, 1])
                
                with col_n:
                    nome_aluno = st.text_input("Nome do Aluno")
                with col_m:
                    matricula_aluno = st.text_input("Matrícula")
                with col_v:
                    st.metric(label="Nota Final", value=f"{nota_calculada:.1f}")
                
                submit = st.form_submit_button("Salvar no Banco de Dados 💾", type="primary")
                
                if submit:
                    if nome_aluno:
                        conn = sqlite3.connect('notas_alunos.db')
                        c = conn.cursor()
                        c.execute("INSERT INTO correcoes (prova_id, nome_aluno, matricula, nota) VALUES (?, ?, ?, ?)", 
                                  (prova_id, nome_aluno, matricula_aluno, nota_calculada))
                        conn.commit()
                        conn.close()
                        st.success(f"Nota de {nome_aluno} salva com sucesso! Pode escanear a próxima.")
                    else:
                        st.error("Digite o nome do aluno antes de salvar.")
        else:
            st.error("❌ Não foi possível ler o QR Code. Fique em um local bem iluminado e alinhe a câmera.")

# ==========================================
# ABA 3: RELATÓRIOS E EXPORTAÇÃO
# ==========================================
with aba_relatorio:
    st.write("Acompanhe o andamento das correções desta sessão.")
    
    if st.button("🔄 Atualizar Relatório"):
        pass 
        
    conn = sqlite3.connect('notas_alunos.db')
    import pandas as pd
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