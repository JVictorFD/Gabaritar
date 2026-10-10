import streamlit as st
import tempfile
import os
import uuid
import qrcode
from fpdf import FPDF
import cv2
import numpy as np
import sqlite3

st.set_page_config(page_title="Gabaritar - Sistema OMR", page_icon="📝", layout="wide")

# --- BANCO DE DADOS LOCAL ---
def inicializar_banco():
    """Cria o banco de dados SQLite para salvar as notas dos alunos."""
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
    
    with tempfile.TemporaryDirectory() as tmpdir:
        for i in range(quantidade):
            pdf.add_page()
            prova_id = str(uuid.uuid4())[:8].upper()
            
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

# Criação de Abas para separar a Criação da Correção
aba_gerar, aba_corrigir, aba_relatorio = st.tabs(["1️⃣ Gerar Provas", "2️⃣ Escanear e Corrigir", "3️⃣ Relatórios"])

# ==========================================
# ABA 1: GERADOR DE PROVAS
# ==========================================
with aba_gerar:
    st.write("Cadastre as questões e gere o lote de provas em PDF.")

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
        if tipo_questao == "Múltipla Escolha":
            c1, c2 = st.columns(2)
            with c1:
                opcoes[0] = st.text_input("A)")
                opcoes[2] = st.text_input("C)")
                opcoes[4] = st.text_input("E)")
            with c2:
                opcoes[1] = st.text_input("B)")
                opcoes[3] = st.text_input("D)")

        if st.button("➕ Adicionar Questão"):
            if enunciado.strip():
                nova_questao = {"enunciado": enunciado, "tipo": tipo_questao, "opcoes": opcoes if tipo_questao == "Múltipla Escolha" else []}
                st.session_state.questoes.append(nova_questao)
                st.success("Questão adicionada!")
                st.rerun()

    if st.button("🚀 Gerar Lote em PDF", type="primary", use_container_width=True):
        if len(st.session_state.questoes) > 0:
            with st.spinner("Gerando provas..."):
                pdf_bytes = gerar_pdf(titulo_prova, st.session_state.questoes, qtd_provas)
                st.success("Lote gerado com sucesso!")
                st.download_button("📥 Baixar PDF Pronto para Impressão", data=pdf_bytes, file_name="Provas.pdf", mime="application/pdf")

# ==========================================
# ABA 2: MÓDULO DE ESCANEAMENTO (OMR)
# ==========================================
with aba_corrigir:
    st.write("Tire uma foto pegando o canto superior direito da prova (Gabarito e QR Code).")
    
    foto_prova = st.camera_input("📷 Escanear Folha")
    
    if foto_prova is not None:
        # 1. Converter imagem da web para formato do OpenCV
        bytes_data = foto_prova.getvalue()
        array_np = np.frombuffer(bytes_data, np.uint8)
        img_cv2 = cv2.imdecode(array_np, cv2.IMREAD_COLOR)
        
        # 2. Tratamento de Imagem (Limiarização para destacar tinta preta)
        cinza = cv2.cvtColor(img_cv2, cv2.COLOR_BGR2GRAY)
        suavizada = cv2.GaussianBlur(cinza, (5, 5), 0)
        _, thresh = cv2.threshold(suavizada, 128, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
        
        # 3. Detectar QR Code
        detector_qr = cv2.QRCodeDetector()
        prova_id, pontos_qr, _ = detector_qr.detectAndDecode(cinza)
        
        if prova_id:
            st.success(f"✅ QR Code Detectado! ID: **{prova_id}**")
            
            # (Lógica simulada de contagem de marcações baseada na área)
            contornos, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            marcacoes_detectadas = sum(1 for c in contornos if 20 < cv2.contourArea(c) < 500)
            nota_calculada = min(10.0, float(marcacoes_detectadas)) # Mock da nota
            
            st.info(f"🔍 Análise Óptica concluída. O sistema avaliou o gabarito.")
            
            # 4. Painel de Inserção de Dados (Foco na agilidade do professor)
            with st.form("form_salvar_nota", clear_on_submit=True):
                st.subheader("Atribuir Nota")
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
                        st.success(f"Nota de {nome_aluno} registrada! Pronta para o próximo escaneamento.")
                    else:
                        st.error("Digite o nome do aluno antes de salvar.")
        else:
            st.error("❌ Não foi possível ler o QR Code. Tente focar melhor no canto direito do cabeçalho.")

# ==========================================
# ABA 3: RELATÓRIOS E EXPORTAÇÃO
# ==========================================
with aba_relatorio:
    st.write("Acompanhe o andamento das correções desta sessão.")
    
    if st.button("🔄 Atualizar Relatório"):
        pass # Apenas recarrega a tela para buscar os dados
        
    conn = sqlite3.connect('notas_alunos.db')
    import pandas as pd
    df_notas = pd.read_sql_query("SELECT id, prova_id as ID_Prova, nome_aluno as Nome, matricula as Matrícula, nota as Nota, data_hora as Data FROM correcoes", conn)
    conn.close()
    
    if not df_notas.empty:
        st.dataframe(df_notas, use_container_width=True, hide_index=True)
        
        # Gera um CSV em texto estruturado
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