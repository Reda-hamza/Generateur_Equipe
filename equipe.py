import streamlit as st
import json
import random
import gspread
import io
import asyncio
from datetime import date, timedelta, datetime
from telegram import Bot
from oauth2client.service_account import ServiceAccountCredentials

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.patches import FancyBboxPatch, PathPatch
from matplotlib.path import Path
import matplotlib.patheffects as pe

# ─── Config page ──────────────────────────────────────────────────────────────
st.set_page_config(page_title="⚽ Brfoot Generator", page_icon="⚽", layout="wide")

st.markdown("""
<style>
    .stApp { background: linear-gradient(135deg, #0a1628, #0e2040, #0a1628); }
    .main-header { text-align: center; padding: 20px; }
    .main-header h1 {
        font-size: 2.5rem; font-weight: 800;
        background: linear-gradient(135deg, #4a9eff, #a8d8ff);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    }
    .user-badge {
        background: rgba(74,158,255,0.15); border: 1px solid rgba(74,158,255,0.3);
        border-radius: 50px; padding: 7px 22px;
        display: inline-block; color: #a8d8ff; font-size: 15px;
    }
    .stButton > button {
        background: linear-gradient(135deg, #1a4a8a, #2563b0);
        color: white; border: 1px solid rgba(74,158,255,0.4);
        border-radius: 12px; padding: 12px 35px;
        font-weight: 700; font-size: 15px; transition: all 0.3s;
    }
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 20px rgba(74,158,255,0.25);
        border-color: rgba(74,158,255,0.7);
    }
    .team-card {
        background: rgba(14,42,92,0.80); border-radius: 14px;
        padding: 16px; margin: 8px 0;
        border: 1px solid rgba(74,158,255,0.20);
    }
    .team-red-card   { border-left: 4px solid #e74c3c; }
    .team-green-card { border-left: 4px solid #27ae60; }
    .player-item {
        background: rgba(255,255,255,0.06); border-radius: 9px;
        padding: 7px 14px; margin: 6px 0;
        display: flex; align-items: center; transition: all 0.2s;
    }
    .player-item:hover { background: rgba(255,255,255,0.10); transform: translateX(4px); }
    .player-num {
        width: 26px; height: 26px; border-radius: 50%;
        display: inline-flex; align-items: center; justify-content: center;
        font-weight: bold; font-size: 12px; margin-right: 11px; flex-shrink: 0;
    }
    .num-red   { background: #e74c3c; color: white; }
    .num-green { background: #27ae60; color: white; }
    .footer { text-align: center; color: rgba(74,158,255,0.35); padding: 20px; font-size: 12px; }
</style>
""", unsafe_allow_html=True)

# ─── Palette & Positions ──────────────────────────────────────────────────────
_BG      = "#0a1628"
_PITCH_D = "#0e2a5c"
_PITCH_L = "#112f6e"
_LINE_C  = "#4a9eff"
_RED_C   = "#e74c3c"
_GRN_C   = "#27ae60"

_POS_RED = [
    (0.50, 0.07),   # GK
    (0.20, 0.25),   # DEF G
    (0.80, 0.25),   # DEF D
    (0.22, 0.42),   # MID G
    (0.78, 0.42),   # MID D
    (0.50, 0.30),   # ATT
]
_POS_GRN = [
    (0.50, 0.93),   # GK
    (0.20, 0.75),   # DEF G
    (0.80, 0.75),   # DEF D
    (0.22, 0.58),   # MID G
    (0.78, 0.58),   # MID D
    (0.50, 0.70),   # ATT
]


# ─── Dessin maillot ───────────────────────────────────────────────────────────

def _draw_jersey(ax, cx, cy, name, color, s=0.056):
    h  = s * 1.30
    hw = s * 0.82
    bw = s * 1.00
    sw = s * 0.50
    sh = s * 0.34
    my = cy + h * 0.16
    MV, LN, CL = Path.MOVETO, Path.LINETO, Path.CLOSEPOLY

    vb = [(cx-hw, cy+h/2), (cx+hw, cy+h/2),
          (cx+bw, cy-h/2), (cx-bw, cy-h/2), (cx-hw, cy+h/2)]
    ax.add_patch(PathPatch(Path(vb, [MV,LN,LN,LN,CL]),
                           fc=color, ec='white', lw=0.9, zorder=5, alpha=0.95))

    vl = [(cx-hw, my+sh*.5), (cx-hw-sw, my),
          (cx-hw-sw*.6, my-sh*.6), (cx-hw, my-sh*.3), (cx-hw, my+sh*.5)]
    ax.add_patch(PathPatch(Path(vl, [MV,LN,LN,LN,CL]),
                           fc=color, ec='white', lw=0.9, zorder=4, alpha=0.95))

    vr = [(cx+hw, my+sh*.5), (cx+hw+sw, my),
          (cx+hw+sw*.6, my-sh*.6), (cx+hw, my-sh*.3), (cx+hw, my+sh*.5)]
    ax.add_patch(PathPatch(Path(vr, [MV,LN,LN,LN,CL]),
                           fc=color, ec='white', lw=0.9, zorder=4, alpha=0.95))

    ax.add_patch(patches.Arc((cx, cy+h/2), hw*0.55, h*0.24,
                              angle=0, theta1=180, theta2=360,
                              color='white', lw=1.3, zorder=6))

    short = name[:8] + "." if len(name) > 8 else name
    ax.text(cx, cy - h/2 - 0.022, short,
            ha='center', va='top', fontsize=10, fontweight='bold',
            color='white', zorder=8,
            path_effects=[pe.withStroke(linewidth=2.2, foreground='black')])


def _draw_pitch(ax):
    ax.add_patch(patches.Rectangle((0,0), 1, 1, color=_PITCH_D, zorder=0))
    for i in range(6):
        if i % 2 == 0:
            ax.add_patch(patches.Rectangle((0, i/6), 1, 1/6, color=_PITCH_L, zorder=0))

    lw = 1.5
    kw = dict(color=_LINE_C, lw=lw, zorder=2, alpha=0.72)
    def l(x0, y0, x1, y1): ax.plot([x0,x1], [y0,y1], **kw)

    l(.04,.02,.96,.02); l(.96,.02,.96,.98)
    l(.96,.98,.04,.98); l(.04,.98,.04,.02)
    l(.04,.50,.96,.50)
    ax.add_patch(patches.Ellipse((.50,.50), .38, .13,
                                  ec=_LINE_C, fc='none', lw=lw, alpha=0.72, zorder=2))
    ax.plot(.50,.50, 'o', color=_LINE_C, ms=3, zorder=2, alpha=0.72)
    l(.24,.02,.24,.18); l(.24,.18,.76,.18); l(.76,.18,.76,.02)
    l(.38,.02,.38,-.005); l(.38,-.005,.62,-.005); l(.62,-.005,.62,.02)
    l(.24,.98,.24,.82); l(.24,.82,.76,.82); l(.76,.82,.76,.98)
    l(.38,.98,.38,1.005); l(.38,1.005,.62,1.005); l(.62,1.005,.62,.98)
    ax.plot(.50,.11, 'o', color=_LINE_C, ms=3, zorder=2, alpha=0.72)
    ax.plot(.50,.89, 'o', color=_LINE_C, ms=3, zorder=2, alpha=0.72)


def generate_lineup_image(team_a: list, team_b: list,
                           score_a: int, score_b: int,
                           week_label: str = "") -> bytes:
    fig = plt.figure(figsize=(6.5, 11), facecolor=_BG, dpi=160)

    ax_h = fig.add_axes([0, 0.915, 1, 0.085])
    ax_h.set_xlim(0,1); ax_h.set_ylim(0,1); ax_h.axis('off')
    ax_h.set_facecolor(_BG)
    ax_h.text(.5, .65, "COMPOSITION",
              ha='center', va='center', fontsize=19, fontweight='bold', color='white')
    ax_h.text(.5, .18,
              week_label or datetime.now().strftime("%d/%m/%Y"),
              ha='center', va='center', fontsize=8, color='#7fb3f5')

    ax = fig.add_axes([0.04, 0.085, 0.92, 0.83])
    ax.set_xlim(0,1); ax.set_ylim(0,1); ax.axis('off')
    _draw_pitch(ax)

    for (x,y), name in zip(_POS_RED, team_a):
        _draw_jersey(ax, x, y, name, _RED_C)
    for (x,y), name in zip(_POS_GRN, team_b):
        _draw_jersey(ax, x, y, name, _GRN_C)

    ax_f = fig.add_axes([0, 0, 1, 0.085])
    ax_f.set_xlim(0,1); ax_f.set_ylim(0,1); ax_f.axis('off')
    ax_f.set_facecolor("#060f1c")

    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=160, bbox_inches='tight', facecolor=_BG)
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()


# ─── TeamGenerator ────────────────────────────────────────────────────────────

class TeamGenerator:
    def __init__(self):
        cfg                 = st.secrets["gsheets"]
        self.spreadsheet_id = cfg["spreadsheet_id"]
        self._gsheet_creds  = dict(cfg)
        self.client         = None
        self.spreadsheet    = None
        self.notes_dict     = {}
        self.load_notes()

    def load_notes(self):
        try:
            with open('notes_joureurs.json', 'r', encoding='utf-8') as f:
                self.notes_dict = {k.upper().strip(): int(v) for k, v in json.load(f).items()}
        except FileNotFoundError:
            self.notes_dict = {}

    def _get_spreadsheet(self):
        if self.spreadsheet is None:
            try:
                scope = ["https://spreadsheets.google.com/feeds",
                         "https://www.googleapis.com/auth/drive"]
                creds = ServiceAccountCredentials.from_json_keyfile_dict(
                    self._gsheet_creds, scope
                )
                self.client      = gspread.authorize(creds)
                self.spreadsheet = self.client.open_by_key(self.spreadsheet_id)
            except Exception as e:
                st.error(f"Erreur connexion Sheets: {e}")
                return None
        return self.spreadsheet

    def fetch_all_data(self, target_week: str):
        ss = self._get_spreadsheet()
        if ss is None:
            return [], []

        present_players = []
        try:
            all_values = ss.sheet1.get_all_values()
            if all_values:
                headers = [h.strip().lower() for h in all_values[0]]
                idx_sem = next((i for i, h in enumerate(headers) if "semaine" in h), -1)
                idx_pre = next((i for i, h in enumerate(headers) if "pres"    in h), -1)
                idx_nom = next((i for i, h in enumerate(headers) if "prenom"  in h), -1)
                if -1 not in [idx_sem, idx_pre, idx_nom]:
                    target_lower = target_week.lower().strip()
                    for row in all_values[1:]:
                        if len(row) <= max(idx_sem, idx_pre, idx_nom):
                            continue
                        if row[idx_sem].strip().lower() != target_lower:
                            continue
                        if row[idx_pre].strip().lower() not in ["present", "présent"]:
                            continue
                        prenom = row[idx_nom].strip().upper()
                        if prenom:
                            if "+" in prenom:
                                present_players.extend(
                                    [n.strip() for n in prenom.split("+") if n.strip()])
                            else:
                                present_players.append(prenom)
            seen = set()
            present_players = [x for x in present_players
                                if not (x in seen or seen.add(x))]
        except Exception as e:
            st.error(f"Erreur lecture feuille présences: {e}")

        linked = []
        try:
            cfg_sheet = ss.worksheet("Configuration")
            for row in cfg_sheet.get_all_values():
                if len(row) >= 2 and row[0].strip().lower() == "linked_players":
                    linked = [p.strip().upper() for p in row[1].split(",") if p.strip()]
                    break
        except gspread.WorksheetNotFound:
            pass
        except Exception as e:
            st.warning(f"Erreur lecture Configuration: {e}")

        return present_players, linked

    def generate_teams(self, players_list: list, linked_players: list):
        team_a, team_b   = [], []
        joueurs_restants = {}

        linked_up = [p.upper().strip() for p in linked_players]
        for nom in players_list:
            if nom.upper().strip() in linked_up:
                team_a.append(nom)
            else:
                joueurs_restants[nom] = self.notes_dict.get(nom.upper().strip(), 0)

        inv_idx = 1
        while (len(team_a) + len(team_b) + len(joueurs_restants)) < 12:
            joueurs_restants[f"Manque_jr {inv_idx}"] = 0
            inv_idx += 1

        for nom, _ in sorted(joueurs_restants.items(), key=lambda x: x[1], reverse=True):
            sa = sum(self.notes_dict.get(n.upper(), 0) for n in team_a)
            sb = sum(self.notes_dict.get(n.upper(), 0) for n in team_b)
            if len(team_a) < 6 and (sa <= sb or len(team_b) >= 6):
                team_a.append(nom)
            elif len(team_b) < 6:
                team_b.append(nom)
            else:
                (team_a if len(team_a) < 6 else team_b).append(nom)

        random.shuffle(team_a)
        random.shuffle(team_b)
        sa = sum(self.notes_dict.get(n.upper(), 0) for n in team_a)
        sb = sum(self.notes_dict.get(n.upper(), 0) for n in team_b)
        return team_a, team_b, sa, sb

    @staticmethod
    def compter_mercredis_restants(date_debut, total_mercredis=52):
        aujourdhui       = datetime.now().date()
        mercredis_passes = 0
        date_courante    = date_debut
        while date_courante <= aujourdhui:
            if date_courante.weekday() == 2:
                mercredis_passes += 1
            date_courante += timedelta(days=1)
        return max(0, total_mercredis - mercredis_passes) + 4

    async def send_to_telegram(self, teams_data: dict, user_name: str,
                                img_bytes: bytes = None) -> bool:
        bot_token = st.secrets["telegram"]["bot_token"]
        chat_id   = st.secrets["telegram"]["chat_id"]
        try:
            bot        = Bot(token=bot_token)
            date_str   = datetime.now().strftime('%d/%m/%Y %H:%M')
            rouge_list = "\n".join(f"  {i}. {p}"
                                   for i, p in enumerate(teams_data['team_a'][:6], 1))
            verte_list = "\n".join(f"  {i}. {p}"
                                   for i, p in enumerate(teams_data['team_b'][:6], 1))
            date_debut = datetime(2025, 4, 23).date()
            restants   = self.compter_mercredis_restants(date_debut)

            caption = (
                f"Composition du {date_str}\n"
                f"Genere par : {user_name}\n\n"
                f"{restants} Seances Restantes"
            )
            if img_bytes:
                await bot.send_photo(chat_id=chat_id,
                                     photo=io.BytesIO(img_bytes),
                                     caption=caption)
            else:
                await bot.send_message(chat_id=chat_id, text=caption)
            return True
        except Exception as e:
            st.error(f"Erreur Telegram: {e}")
            return False


# ─── Helpers Streamlit ────────────────────────────────────────────────────────

def _load_teams(generator: TeamGenerator) -> bool:
    current_week = datetime.now().isocalendar()[1]
    players, linked = generator.fetch_all_data(f"Semaine {current_week}")
    if not players:
        return False
    ta, tb, sa, sb = generator.generate_teams(players, linked)
    st.session_state.current_teams = {
        'team_a': ta, 'team_b': tb, 'score_a': sa, 'score_b': sb,
        'week': current_week
    }
    st.session_state.players_list = players
    st.session_state.pop('lineup_img', None)
    return True


def _get_or_build_image() -> bytes:
    if 'lineup_img' not in st.session_state:
        teams = st.session_state.current_teams
        week  = teams.get('week', datetime.now().isocalendar()[1])
        st.session_state.lineup_img = generate_lineup_image(
            teams['team_a'], teams['team_b'],
            teams['score_a'], teams['score_b'],
            week_label=f"Semaine {week} - {datetime.now().strftime('%d/%m/%Y')}"
        )
    return st.session_state.lineup_img


# ─── Fenêtre modale (st.dialog) ───────────────────────────────────────────────

@st.dialog("📤 Envoyer la composition")
def dialog_envoi(generator, teams):
    """Vraie fenêtre modale centrée — s'ouvre au clic sur le bouton Telegram."""
    st.markdown(
        "<p style='color:#a8d8ff; margin-bottom:4px;'>"
        "Entrez votre prénom pour identifier qui a généré cette composition.</p>",
        unsafe_allow_html=True
    )
    nom_saisi = st.text_input("Votre prénom", placeholder="Ex: Karim",
                               label_visibility="visible")

    col_ok, col_cancel = st.columns(2)
    with col_ok:
        if st.button("✅ Confirmer & Envoyer", use_container_width=True, type="primary"):
            if nom_saisi.strip():
                with st.spinner("Génération de l'image..."):
                    img = _get_or_build_image()
                with st.spinner("Envoi sur Telegram..."):
                    ok = asyncio.run(generator.send_to_telegram(
                        teams, nom_saisi.strip(), img
                    ))
                st.session_state.pop('lineup_img', None)
                if ok:
                    st.session_state['telegram_result'] = ('ok', nom_saisi.strip())
                else:
                    st.session_state['telegram_result'] = ('err', '')
                st.rerun()
            else:
                st.warning("⚠️ Veuillez saisir votre prénom.")
    with col_cancel:
        if st.button("✖ Annuler", use_container_width=True):
            st.rerun()


# ─── Interface ────────────────────────────────────────────────────────────────

def main():
    st.markdown("""
    <div class="main-header">
        <h1>⚽ TEAM GENERATOR PRO ⚽</h1>
        <p style="font-size:16px; color:#7fb3f5; margin-top:4px;">Génération automatique et équilibrée</p>
    </div>
    """, unsafe_allow_html=True)

    if 'generator' not in st.session_state:
        st.session_state.generator = TeamGenerator()
    generator = st.session_state.generator

    if 'user_name' not in st.session_state:
        st.session_state.user_name = st.query_params.get("user", "Joueur")

    _, col_c, _ = st.columns([1, 2, 1])
    with col_c:
        st.markdown(f"""
        <div style="text-align:center; margin-bottom:14px;">
            <span class="user-badge">👋 Bienvenue, <strong>{st.session_state.user_name}</strong></span>
        </div>
        """, unsafe_allow_html=True)

    if 'current_teams' not in st.session_state:
        with st.spinner("🎲 Chargement des joueurs..."):
            if not _load_teams(generator):
                st.error("❌ Aucun joueur trouvé pour cette semaine")
                return

    teams = st.session_state.current_teams

    # ── Résultat envoi Telegram (affiché après fermeture du dialog) ───────────
    result = st.session_state.pop('telegram_result', None)
    if result:
        if result[0] == 'ok':
            st.success(f"✅ Composition envoyée par {result[1]} !")
            st.balloons()
        else:
            st.error("❌ Erreur d'envoi Telegram")

    # ── Boutons principaux ────────────────────────────────────────────────────
    _, c2, c3, _ = st.columns([1, 2, 2, 1])

    with c2:
        if st.button("🔄 RÉGÉNÉRER", use_container_width=True):
            with st.spinner("Génération..."):
                if _load_teams(generator):
                    st.rerun()
                else:
                    st.error("❌ Erreur de chargement")

    with c3:
        # Un seul clic ouvre la vraie fenêtre modale
        if st.button("📤 ENVOYER TELEGRAM", use_container_width=True):
            dialog_envoi(generator, teams)

    # ── Note d'information ────────────────────────────────────────────────────
    st.markdown("""
    <div style="
        background: rgba(74,158,255,0.07);
        border-left: 3px solid rgba(74,158,255,0.50);
        border-radius: 0 10px 10px 0;
        padding: 14px 18px;
        margin: 18px 0 10px;
        color: #a8d8ff;
        font-size: 13.5px;
        line-height: 1.6;
    ">
        ℹ️ L'application récupère la liste des joueurs ayant voté <strong>"oui"</strong>
        sur le groupe Telegram, puis compose les équipes en essayant de les équilibrer
        au maximum.<br>
        Si vous souhaitez ajouter un joueur, commentez dans le groupe avec le signe
        <strong>"+"</strong> suivi du nom du joueur (exemple : <strong>+Kamel</strong>),
        et ce <strong>au moins une heure avant</strong> de lancer l'application.
    </div>
    """, unsafe_allow_html=True)

    # ── Listes joueurs ────────────────────────────────────────────────────────
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("""
        <div class="team-card team-red-card">
            <h3 style="color:#e74c3c; text-align:center; margin:0 0 10px; font-size:1.1rem;">
                🔴 ÉQUIPE ROUGE
            </h3>
        </div>
        """, unsafe_allow_html=True)
        for i, player in enumerate(teams['team_a'][:6], 1):
            st.markdown(f"""
            <div class="player-item">
                <div class="player-num num-red">{i}</div>
                <strong style="color:white;">{player}</strong>
            </div>
            """, unsafe_allow_html=True)

    with col2:
        st.markdown("""
        <div class="team-card team-green-card">
            <h3 style="color:#27ae60; text-align:center; margin:0 0 10px; font-size:1.1rem;">
                🟢 ÉQUIPE VERTE
            </h3>
        </div>
        """, unsafe_allow_html=True)
        for i, player in enumerate(teams['team_b'][:6], 1):
            st.markdown(f"""
            <div class="player-item">
                <div class="player-num num-green">{i}</div>
                <strong style="color:white;">{player}</strong>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("""
    <div class="footer">⚽ Team Generator Pro — Génération équilibrée automatique</div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()