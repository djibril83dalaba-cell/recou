import streamlit as st
import pandas as pd
import os
import plotly.express as px # Pour les graphiques

# --- CONFIGURATION ---
FILE_NAME = "gestion_recouvrement_gnf.csv"
st.set_page_config(page_title="Recouvrement GNF Pro", layout="wide")

def load_data():
    if os.path.exists(FILE_NAME):
        df = pd.read_csv(FILE_NAME)
        for col in ["Total TTC", "Avance client", "Solde dû"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
        return df
    else:
        columns = ["Type", "Etat", "Statut", "Référence", "Date", "Intitulé client", 
                   "Entête 1", "Date livraison", "Total TTC", "Avance client", "Solde dû"]
        return pd.DataFrame(columns=columns)

if 'df' not in st.session_state:
    st.session_state.df = load_data()

def style_solde(val):
    color = 'red' if val > 0 else 'green'
    return f'color: {color}; font-weight: bold'

# --- INTERFACE ---
st.title("🇬🇳 Pilotage Recouvrement GNF")

# --- BARRE LATÉRALE ---
st.sidebar.header("📁 Importation & Actions")
uploaded_file = st.sidebar.file_uploader("Importer Excel (.xlsx)", type=["xlsx"])

if uploaded_file:
    try:
        df_import = pd.read_excel(uploaded_file)
        required = ["Type", "Référence", "Intitulé client", "Total TTC"]
        if all(c in df_import.columns for c in required):
            if "Solde dû" not in df_import.columns:
                df_import["Solde dû"] = df_import["Total TTC"]
            
            df_import = df_import[df_import["Solde dû"] > 0] # Supprimer lignes soldées
            df_import["Avance client"] = df_import["Total TTC"] - df_import["Solde dû"]
            
            if st.sidebar.button("Confirmer l'import"):
                st.session_state.df = pd.concat([st.session_state.df, df_import]).drop_duplicates(subset=['Référence'], keep='last')
                st.session_state.df.to_csv(FILE_NAME, index=False)
                st.sidebar.success("Données importées !")
                st.rerun()
    except Exception as e:
        st.sidebar.error(f"Erreur : {e}")

menu = st.sidebar.radio("Navigation", ["Tableau de Bord & Stats", "Liste des Factures", "Synthèse par Client", "Enregistrer un Règlement"])

# --- FILTRAGE RECHERCHE ---
search_query = st.text_input("🔍 Rechercher un client ou une référence...", "")
df_final = st.session_state.df.copy()
if search_query:
    df_final = df_final[df_final.astype(str).apply(lambda x: x.str.contains(search_query, case=False)).any(axis=1)]

# --- 1. STATISTIQUES ---
if menu == "Tableau de Bord & Stats":
    st.subheader("📊 Indicateurs Clés de Performance")
    
    if not df_final.empty:
        total_facture = df_final["Total TTC"].sum()
        total_encaisse = df_final["Avance client"].sum()
        total_du = df_final["Solde dû"].sum()
        taux_recouvrement = (total_encaisse / total_facture * 100) if total_facture > 0 else 0

        # Métriques
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Facturé", f"{total_facture:,.0f} GNF")
        c2.metric("Total Encaissé", f"{total_encaisse:,.0f} GNF", delta=f"{taux_recouvrement:.1f}%", delta_color="normal")
        c3.metric("Reste à Recouvrer", f"{total_du:,.0f} GNF", delta_color="inverse")
        c4.metric("Nb Factures", len(df_final))

        st.divider()

        # Graphiques
        col_g1, col_g2 = st.columns(2)

        with col_g1:
            st.write("📈 **Répartition Encaissé vs Restant**")
            fig_pie = px.pie(values=[total_encaisse, total_du], names=["Encaissé", "Reste à payer"], 
                             color_discrete_sequence=["#2ecc71", "#e74c3c"], hole=0.4)
            st.plotly_chart(fig_pie, use_container_width=True)

        with col_g2:
            st.write("🏆 **Top 5 des plus gros débiteurs (Clients)**")
            top_clients = df_final.groupby("Intitulé client")["Solde dû"].sum().sort_values(ascending=False).head(5).reset_index()
            fig_bar = px.bar(top_clients, x="Intitulé client", y="Solde dû", text_auto='.2s', color="Solde dû", color_continuous_scale="Reds")
            st.plotly_chart(fig_bar, use_container_width=True)
    else:
        st.info("Ajoutez des données pour voir les statistiques.")

# --- 2. LISTE DÉTAILLÉE ---
elif menu == "Liste des Factures":
    st.subheader("📋 Liste des factures")
    if not df_final.empty:
        st.dataframe(
            df_final.style.map(style_solde, subset=['Solde dû'])
            .format({"Total TTC": "{:,.0f} GNF", "Avance client": "{:,.0f} GNF", "Solde dû": "{:,.0f} GNF"}),
            use_container_width=True
        )

# --- 3. SYNTHÈSE CLIENT ---
elif menu == "Synthèse par Client":
    st.subheader("👥 Solde par compte")
    if not df_final.empty:
        df_grouped = df_final.groupby("Intitulé client").agg({"Référence": "count", "Total TTC": "sum", "Avance client": "sum", "Solde dû": "sum"})
        st.dataframe(
            df_grouped.style.map(style_solde, subset=['Solde dû'])
            .format({"Total TTC": "{:,.0f} GNF", "Avance client": "{:,.0f} GNF", "Solde dû": "{:,.0f} GNF"}),
            use_container_width=True
        )

# --- 4. RÈGLEMENT ---
elif menu == "Enregistrer un Règlement":
    st.subheader("💰 Paiement")
    df_ouvert = st.session_state.df[st.session_state.df["Solde dû"] > 0]
    if not df_ouvert.empty:
        c_sel = st.selectbox("Client", sorted(df_ouvert["Intitulé client"].unique()))
        r_sel = st.selectbox("Facture", df_ouvert[df_ouvert["Intitulé client"] == c_sel]["Référence"].tolist())
        row = df_ouvert[df_ouvert["Référence"] == r_sel].iloc[0]
        
        with st.form("pay"):
            montant = st.number_input(f"Montant (Reste: {row['Solde dû']:,.0f} GNF)", min_value=0.0, step=10000.0)
            if st.form_submit_button("Valider"):
                idx = st.session_state.df[st.session_state.df["Référence"] == r_sel].index[0]
                st.session_state.df.at[idx, "Solde dû"] -= montant
                st.session_state.df.at[idx, "Avance client"] = st.session_state.df.at[idx, "Total TTC"] - st.session_state.df.at[idx, "Solde dû"]
                st.session_state.df.at[idx, "Statut"] = "Soldé" if st.session_state.df.at[idx, "Solde dû"] <= 0 else "Partiel"
                st.session_state.df.to_csv(FILE_NAME, index=False)
                st.success("Paiement enregistré !")
                st.rerun()