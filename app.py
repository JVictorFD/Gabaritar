import streamlit as st
import tempfile
import os
import uuid
import qrcode
from fpdf import FPDF

st.set_page_config(page_title="Gerador de Provas - Gabaritar", page_icon="📝", layout="wide")

def higienizar_texto(texto):
    """
    Garante que acentos do português funcionem sem travar o FPDF.
    """
    return str(texto).encode('latin-1', 'replace').decode('latin-1')

def gerar_pdf(titulo, questoes, quantidade):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        for i in range(quantidade):
            pdf.add_page()
            prova_id = str(uuid.uuid4())[:8].upper()
            
            # --- 1. Criar QR Code Temporário ---
            qr_path = os.path.join(tmpdir, f"qr_{i}.png")
            qr = qrcode.QRCode(version=1, box_size=5, border=1)
            qr.add_data(prova_id)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            img.save(qr_path)
            
            # --- 2. Título (Centralizado no Topo) ---
            pdf.set_font("Arial", "B", 16)
            pdf.cell(0, 10, higienizar_texto(titulo), ln=1, align="C")
            pdf.ln(2)
            
            # Ponto de Ancoragem: Salva a posição Y exata logo após o título
            y_ancora = pdf.get_y()
            
            # --- 3. Dados do Aluno (Coluna da Esquerda) ---
            pdf.set_font("Arial", "", 11)
            pdf.set_xy(10, y_ancora) # Força o cursor para a esquerda, abaixo do título
            pdf.cell(90, 7, higienizar_texto("Nome: ______________________________________"), ln=1)
            pdf.cell(90, 7, higienizar_texto("Matrícula: _________________   Turma: _________"), ln=1)
            
            pdf.set_font("Arial", "B", 10)
            pdf.cell(90, 7, higienizar_texto(f"ID Exclusivo da Prova: {prova_id}"), ln=1)
            y_fim_aluno = pdf.get_y() # Salva onde os textos do aluno terminaram
            
            # --- 4. Gabarito Dinâmico (Coluna Central) ---
            multiplas = [q for q in questoes if q['tipo'] == 'Múltipla Escolha']
            y_fim_gabarito = y_ancora
            
            if multiplas:
                altura_gab = 10 + (5 * len(multiplas))
                # Desenha a caixa ancorada perfeitamente no eixo Y inicial
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
            
            # --- 5. QR Code (Coluna da Direita) ---
            # Posicionado na extrema direita, usando a mesma âncora Y do topo
            pdf.image(qr_path, x=175, y=y_ancora, w=25)
            y_fim_qr = y_ancora + 25
            
            # --- 6. Linha Separadora Inteligente ---
            # A linha horizontal vai se adaptar ao elemento que for mais "comprido" (aluno, gabarito ou QR code)
            pos_y_linha = max(y_fim_aluno, y_fim_gabarito, y_fim_qr) + 5
            pdf.set_y(pos_y_linha)
            pdf.line(10, pdf.get_y(), 200, pdf.get_y())
            pdf.ln(5)
            
            # --- 7. Renderização Segura das Questões ---
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
st.title("📝 Gabaritar - Criador de Provas")
st.write("Cadastre as questões, gere o lote em PDF com QR Codes e gabaritos automáticos.")

if 'questoes' not in st.session_state:
    st.session_state.questoes = []

with st.sidebar:
    st.header("⚙️ Configurações do Lote")
    titulo_prova = st.text_input("Título da Avaliação", "Prova de Conhecimentos Gerais")
    qtd_provas = st.number_input("Quantidade de Provas (Cópias Únicas)", min_value=1, max_value=500, value=1)
    
    st.markdown("---")
    st.info(f"📊 Questões no banco atual: **{len(st.session_state.questoes)}**")

st.subheader("Adicionar Nova Questão")
tipo_questao = st.radio("Selecione o Tipo de Questão:", ["Múltipla Escolha", "Textual (Discursiva)"], horizontal=True)
enunciado = st.text_area("Enunciado da Questão", placeholder="Digite a pergunta real com espaços aqui...")

opcoes = ["", "", "", "", ""]
if tipo_questao == "Múltipla Escolha":
    st.write("Preencha as alternativas:")
    col1, col2 = st.columns(2)
    with col1:
        opcoes[0] = st.text_input("Opção A")
        opcoes[2] = st.text_input("Opção C")
        opcoes[4] = st.text_input("Opção E")
    with col2:
        opcoes[1] = st.text_input("Opção B")
        opcoes[3] = st.text_input("Opção D")

if st.button("➕ Adicionar à Prova"):
    if enunciado.strip():
        nova_questao = {
            "enunciado": enunciado,
            "tipo": tipo_questao,
            "opcoes": opcoes if tipo_questao == "Múltipla Escolha" else []
        }
        st.session_state.questoes.append(nova_questao)
        st.success("Questão adicionada com sucesso!")
        st.rerun()
    else:
        st.warning("Por favor, preencha o enunciado antes de adicionar.")

st.markdown("---")

if st.session_state.questoes:
    st.subheader("Visualização da Prova")
    for i, q in enumerate(st.session_state.questoes):
        with st.expander(f"Questão {i+1}: {q['enunciado'][:40]}... ({q['tipo']})"):
            st.write(f"**Pergunta:** {q['enunciado']}")
            if q['tipo'] == 'Múltipla Escolha':
                letras = ['A', 'B', 'C', 'D', 'E']
                for idx, opt in enumerate(q['opcoes']):
                    if opt: st.write(f"**{letras[idx]})** {opt}")
            if st.button(f"Remover Questão {i+1}", key=f"del_{i}"):
                st.session_state.questoes.pop(i)
                st.rerun()

st.markdown("---")

if st.button("🚀 Gerar Lote de Provas (PDF)", type="primary", use_container_width=True):
    if len(st.session_state.questoes) == 0:
        st.error("Adicione pelo menos uma questão para gerar o documento.")
    else:
        with st.spinner(f"Gerando {qtd_provas} prova(s) estruturada(s)..."):
            pdf_bytes = gerar_pdf(titulo_prova, st.session_state.questoes, qtd_provas)
            
            st.success("✨ Lote gerado com sucesso sem sobreposições!")
            st.download_button(
                label="📥 Baixar Arquivo PDF Pronto para Impressão",
                data=pdf_bytes,
                file_name=f"Provas_{titulo_prova.replace(' ', '_')}.pdf",
                mime="application/pdf"
            )