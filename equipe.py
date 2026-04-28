import streamlit as st
import json
import random
import gspread
import io
import asyncio
from datetime import date, timedelta, datetime
from zoneinfo import ZoneInfo

TZ_ALGER = ZoneInfo('Africa/Algiers')   # UTC+1

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
st.set_page_config(page_title="⚽ Team Generator Pro", page_icon="⚽", layout="wide")

st.markdown("""
<style>
    /* ── Masquer éléments Streamlit natifs ── */
    #MainMenu         { visibility: hidden; }
    header            { visibility: hidden; }
    footer            { visibility: hidden; }
    [data-testid="stToolbar"]          { display: none !important; }
    [data-testid="manage-app-button"]  { display: none !important; }
    .stDeployButton                    { display: none !important; }

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
    .blocked-banner {
        background: rgba(231,76,60,0.15); border: 1px solid rgba(231,76,60,0.5);
        border-radius: 12px; padding: 14px 20px; margin: 10px 0;
        color: #ff8a80; font-size: 14px; text-align: center;
    }
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

# ─── Noms des feuilles Sheets ─────────────────────────────────────────────────
_SHEET_ENVOI = "EnvoiLog"
_SHEET_LOGS  = "UsageLogs"


# ─── Dessin maillot ───────────────────────────────────────────────────────────

def _draw_jersey(ax, cx, cy, name, color, s=0.056):
    h  = s * 1.30
    hw = s * 0.82
    bw = s * 1.00
    sw = s * 0.55
    sh = s * 0.90
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
                           week_label: str = "",
                           user_name: str = "") -> bytes:
    fig = plt.figure(figsize=(6.5, 11), facecolor=_BG, dpi=160)

    ax_h = fig.add_axes([0, 0.915, 1, 0.085])
    ax_h.set_xlim(0,1); ax_h.set_ylim(0,1); ax_h.axis('off')
    ax_h.set_facecolor(_BG)
    date_str = datetime.now(TZ_ALGER).strftime("%d/%m/%Y")
    ax_h.text(.5, .65, f"COMPOSITION DU {date_str}",
              ha='center', va='center', fontsize=16, fontweight='bold', color='white')
    if user_name:
        ax_h.text(.5, .18, f"Generé par : {user_name}",
                  ha='center', va='center', fontsize=11, color='#7fb3f5')

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
                self.notes_dict = {k.upper().strip(): int(v)
                                   for k, v in json.load(f).items()}
        except FileNotFoundError:
            self.notes_dict = {}

    def _get_spreadsheet(self):
        if self.spreadsheet is None:
            try:
                scope = ["https://spreadsheets.google.com/feeds",
                         "https://www.googleapis.com/auth/drive"]
                creds = ServiceAccountCredentials.from_json_keyfile_dict(
                    self._gsheet_creds, scope)
                self.client      = gspread.authorize(creds)
                self.spreadsheet = self.client.open_by_key(self.spreadsheet_id)
            except Exception as e:
                st.error(f"Erreur connexion Sheets: {e}")
                return None
        return self.spreadsheet

    def _get_or_create_sheet(self, name: str, headers: list):
        ss = self._get_spreadsheet()
        if ss is None:
            return None
        try:
            return ss.worksheet(name)
        except gspread.WorksheetNotFound:
            ws = ss.add_worksheet(title=name, rows=1000, cols=len(headers))
            ws.append_row(headers)
            return ws

    def fetch_all_data(self, target_week: str):
        ss = self._get_spreadsheet()
        if ss is None:
            return [], []

        present_players = []
        try:
            all_values = ss.sheet1.get_all_values()
            if all_values:
                headers = [h.strip().lower() for h in all_values[0]]
                idx_sem = next((i for i,h in enumerate(headers) if "semaine" in h), -1)
                idx_pre = next((i for i,h in enumerate(headers) if "pres"    in h), -1)
                idx_nom = next((i for i,h in enumerate(headers) if "prenom"  in h), -1)
                if -1 not in [idx_sem, idx_pre, idx_nom]:
                    target_lower = target_week.lower().strip()
                    for row in all_values[1:]:
                        if len(row) <= max(idx_sem, idx_pre, idx_nom):
                            continue
                        if row[idx_sem].strip().lower() != target_lower:
                            continue
                        if row[idx_pre].strip().lower() not in ["present","présent"]:
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
            st.error(f"Erreur lecture présences: {e}")

        linked = []
        try:
            cfg_ws = ss.worksheet("Configuration")
            for row in cfg_ws.get_all_values():
                if len(row) >= 2 and row[0].strip().lower() == "linked_players":
                    linked = [p.strip().upper() for p in row[1].split(",") if p.strip()]
                    break
        except gspread.WorksheetNotFound:
            pass
        except Exception as e:
            st.warning(f"Erreur lecture Configuration: {e}")

        return present_players, linked

def generate_teams(self, players_list: list, linked_players: list):
    team_a, team_b = [], []
    joueurs_restants = {}
    linked_up = [p.upper().strip() for p in linked_players]
    
    # Séparer linked et non-linked
    linked_list = []
    free_list = []
    
    for nom in players_list:
        if nom.upper().strip() in linked_up:
            linked_list.append(nom)
        else:
            free_list.append(nom)
    
    # Ajouter des joueurs manquants si nécessaire
    inv_idx = 1
    while (len(linked_list) + len(free_list)) < 12:
        free_list.append(f"Manque_jr {inv_idx}")
        inv_idx += 1
    
    # Mélanger les joueurs libres avant distribution
    random.shuffle(free_list)
    
    # Répartir équitablement les joueurs liés entre les deux équipes
    random.shuffle(linked_list)  # Mélanger aussi les liés
    for i, nom in enumerate(linked_list):
        if i % 2 == 0:
            team_a.append(nom)
        else:
            team_b.append(nom)
    
    # Distribuer les joueurs libres aléatoirement mais équitablement
    for nom in free_list:
        note = self.notes_dict.get(nom.upper().strip(), 0)
        sa = sum(self.notes_dict.get(n.upper().strip(), 0) for n in team_a)
        sb = sum(self.notes_dict.get(n.upper().strip(), 0) for n in team_b)
        
        # Ajouter un facteur aléatoire pour varier quand c'est équilibré
        if len(team_a) < 6 and len(team_b) < 6:
            # Choix pondéré basé sur les notes + aléatoire
            diff = sa - sb
            prob_a = 0.5 + (random.random() * 0.3)  # Base 50-80% de chance d'équipe A
            if diff > 0:  # Team A plus forte
                prob_a = 0.3  # 30% de chance d'aller en A
            elif diff < 0:  # Team B plus forte
                prob_a = 0.7  # 70% de chance d'aller en A
            
            if random.random() < prob_a:
                team_a.append(nom)
            else:
                team_b.append(nom)
        elif len(team_a) < 6:
            team_a.append(nom)
        else:
            team_b.append(nom)
    
    # Mélanger l'ordre final
    random.shuffle(team_a)
    random.shuffle(team_b)
    
    sa = sum(self.notes_dict.get(n.upper().strip(), 0) for n in team_a)
    sb = sum(self.notes_dict.get(n.upper().strip(), 0) for n in team_b)
    
    return team_a, team_b, sa, sb


    def check_envoi_today(self) -> tuple[bool, str]:
        try:
            ws = self._get_or_create_sheet(
                _SHEET_ENVOI, ["date", "heure", "envoyeur", "equipe_rouge", "equipe_verte"])
            if ws is None:
                return False, ""
            rows = ws.get_all_values()
            today_str = datetime.now(TZ_ALGER).strftime("%Y-%m-%d")
            for row in rows[1:]:
                if row and row[0].strip() == today_str:
                    envoyeur = row[2].strip() if len(row) > 2 else "Anonyme"
                    return True, envoyeur
        except Exception as e:
            st.warning(f"Impossible de vérifier EnvoiLog: {e}")
        return False, ""

    def log_envoi(self, user_name: str, teams_data: dict):
        try:
            ws = self._get_or_create_sheet(
                _SHEET_ENVOI, ["date", "heure", "envoyeur", "equipe_rouge", "equipe_verte"])
            if ws is None:
                return
            rouge = ", ".join(teams_data['team_a'][:6])
            verte = ", ".join(teams_data['team_b'][:6])
            ws.append_row([
                datetime.now(TZ_ALGER).strftime("%Y-%m-%d"),
                datetime.now(TZ_ALGER).strftime("%H:%M:%S"),
                user_name, rouge, verte,
            ])
        except Exception as e:
            st.warning(f"Impossible d'écrire dans EnvoiLog: {e}")

    def log_usage(self, action: str, user_name: str, teams_data: dict = None):
        try:
            ws = self._get_or_create_sheet(
                _SHEET_LOGS,
                ["timestamp", "action", "utilisateur", "equipe_rouge", "equipe_verte"])
            if ws is None:
                return
            rouge = ", ".join(teams_data['team_a'][:6]) if teams_data else ""
            verte = ", ".join(teams_data['team_b'][:6]) if teams_data else ""
            ws.append_row([
                datetime.now(TZ_ALGER).strftime("%Y-%m-%d %H:%M:%S"),
                action, user_name, rouge, verte,
            ])
        except Exception as e:
            st.warning(f"Impossible d'écrire dans UsageLogs: {e}")

    @staticmethod
    def compter_mercredis_restants(date_debut, total_mercredis=52):
        aujourdhui       = datetime.now(TZ_ALGER).date()
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
            rouge_list = "\n".join(f"  {i}. {p}"
                                   for i,p in enumerate(teams_data['team_a'][:6], 1))
            verte_list = "\n".join(f"  {i}. {p}"
                                   for i,p in enumerate(teams_data['team_b'][:6], 1))
            date_debut = datetime(2025, 4, 23).date()
            restants   = self.compter_mercredis_restants(date_debut)
            caption = (
                f"Genere par : {user_name}\n"
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
    """Charge joueurs + équipes SANS log (le log est fait explicitement au clic)."""
    current_week = datetime.now(TZ_ALGER).isocalendar()[1]
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


def _get_or_build_image(user_name: str = "") -> bytes:
    """Génère l'image seulement si absente du cache, en passant le nom."""
    if 'lineup_img' not in st.session_state:
        teams = st.session_state.current_teams
        week  = teams.get('week', datetime.now(TZ_ALGER).isocalendar()[1])
        st.session_state.lineup_img = generate_lineup_image(
            teams['team_a'], teams['team_b'],
            teams['score_a'], teams['score_b'],
            week_label=f"Semaine {week} - {datetime.now(TZ_ALGER).strftime('%d/%m/%Y')}",
            user_name=user_name,
        )
    return st.session_state.lineup_img


# ─── Fenêtre modale ───────────────────────────────────────────────────────────

@st.dialog("📤 Envoyer la composition")
def dialog_envoi(generator: TeamGenerator, teams: dict):
    aujourd_hui = datetime.now(TZ_ALGER)

    # ── Vérification 1 : uniquement le mercredi ───────────────────────────────
    if aujourd_hui.weekday() != 2:
        jours_fr = ["lundi","mardi","mercredi","jeudi","vendredi","samedi","dimanche"]
        jour_actuel = jours_fr[aujourd_hui.weekday()]
        jours_avant = (2 - aujourd_hui.weekday()) % 7
        prochain    = (aujourd_hui + timedelta(days=jours_avant)).strftime("%d/%m/%Y")
        st.markdown(f"""
        <div class="blocked-banner">
            📅 L'envoi est autorisé <strong>uniquement le mercredi</strong>.<br>
            Aujourd'hui c'est <strong>{jour_actuel}</strong> —
            prochain mercredi le <strong>{prochain}</strong>.
        </div>
        """, unsafe_allow_html=True)
        if st.button("✖ Fermer", use_container_width=True):
            st.rerun()
        return

    # ── Vérification 2 : pas déjà envoyé ce mercredi ─────────────────────────
    deja_envoye, envoyeur_du_jour = generator.check_envoi_today()
    if deja_envoye:
        st.markdown(f"""
        <div class="blocked-banner">
            🔒 La composition a déjà été envoyée ce mercredi par
            <strong>{envoyeur_du_jour}</strong>.<br>
            Un seul envoi est autorisé par mercredi.
        </div>
        """, unsafe_allow_html=True)
        if st.button("✖ Fermer", use_container_width=True):
            st.rerun()
        return

    # ── Saisie du nom (optionnel) ─────────────────────────────────────────────
    st.markdown(
        "<p style='color:#a8d8ff; margin-bottom:4px;'>"
        "Tapez votre prénom, ou laissez vide pour rester anonyme.</p>",
        unsafe_allow_html=True
    )
    nom_saisi = st.text_input(
        "Votre prénom (optionnel)",
        placeholder="Ex: Karim  —  ou laisser vide pour Anonyme"
    )

    col_ok, col_cancel = st.columns(2)
    with col_ok:
        if st.button("✅ Envoyer", use_container_width=True, type="primary"):
            user_name = nom_saisi.strip() if nom_saisi.strip() else "Anonyme"

            with st.spinner("Génération de l'image..."):
                # FIX : passer user_name pour l'afficher dans l'image
                img = _get_or_build_image(user_name=user_name)
            with st.spinner("Envoi sur Telegram..."):
                ok = asyncio.run(generator.send_to_telegram(teams, user_name, img))

            if ok:
                generator.log_envoi(user_name, teams)
                generator.log_usage("envoi_telegram", user_name, teams)
                st.session_state.pop('lineup_img', None)
                st.session_state['telegram_result'] = ('ok', user_name)
            else:
                st.session_state['telegram_result'] = ('err', '')
            st.rerun()

    with col_cancel:
        if st.button("✖ Annuler", use_container_width=True):
            st.rerun()


# ─── Interface principale ─────────────────────────────────────────────────────

def main():
    st.markdown("""
    <div class="main-header">
        <h1>⚽ BRFOOT GENERATOR ⚽</h1>
    </div>
    """, unsafe_allow_html=True)

    # Generator mis en cache — évite reconnexion OAuth à chaque rerun
    if 'generator' not in st.session_state:
        st.session_state.generator = TeamGenerator()
    generator = st.session_state.generator

    if 'user_name' not in st.session_state:
        st.session_state.user_name = st.query_params.get("user", "Anonyme")

    # Chargement initial — sans log
    if 'current_teams' not in st.session_state:
        with st.spinner("🎲 Chargement des joueurs..."):
            if not _load_teams(generator):
                st.error("❌ Aucun joueur trouvé pour cette semaine")
                return

    teams = st.session_state.current_teams

    # Résultat de l'envoi Telegram
    result = st.session_state.pop('telegram_result', None)
    if result:
        if result[0] == 'ok':
            nom_aff = result[1] if result[1] != "Anonyme" else "un joueur anonyme"
            st.success(f"✅ Composition envoyée par {nom_aff} !")
            st.balloons()
        else:
            st.error("❌ Erreur d'envoi Telegram")

    # ── Boutons ───────────────────────────────────────────────────────────────
    _, c2, c3, _ = st.columns([1, 2, 2, 1])

    with c2:
        if st.button("🔄 RÉGÉNÉRER", use_container_width=True):
            with st.spinner("Génération..."):
                if _load_teams(generator):
                    # Log UNIQUEMENT sur clic humain explicite
                    # Le flag évite tout double-log si Streamlit rerun juste après
                    st.session_state['_pending_log_regen'] = True
                    st.rerun()
                else:
                    st.error("❌ Erreur de chargement")

    # Traiter le log après rerun (hors du bloc bouton pour éviter les reruns en boucle)
    if st.session_state.pop('_pending_log_regen', False):
        generator.log_usage("regeneration",
                            st.session_state.user_name,
                            st.session_state.current_teams)

    with c3:
        if st.button("📤 ENVOYER TELEGRAM", use_container_width=True):
            dialog_envoi(generator, teams)

    # ── Expander Info (défile en dessous au clic) ────────────────────────────
    with st.expander("ℹ️ Comment ça marche ?", expanded=False):
        st.markdown("""
        <div style="color:#a8d8ff; font-size:13.5px; line-height:1.8; padding:4px 0;">

        <p><strong style="color:white;">🔄 Régénération</strong><br>
        Vous pouvez régénérer la composition plusieurs fois. 
        Une fois que vous avez fait votre choix final, envoyez la composition finale
        sur Telegram.</p>

        <p><strong style="color:white;">📤 Envoi Telegram</strong><br>
        L'envoi est autorisé <strong>uniquement le mercredi</strong>. Une seule
        composition peut être envoyée par mercredi — après l'envoi, le bouton est
        bloqué pour tout le monde jusqu'au mercredi suivant.</p>

        <p><strong style="color:white;">✅ Joueurs présents</strong><br>
        L'application récupère automatiquement la liste des joueurs ayant voté
        <strong>"oui"</strong> sur le groupe Telegram.</p>

        <p><strong style="color:white;">➕ Ajouter un joueur manuellement</strong><br>
        Commentez dans le groupe Telegram avec le signe
        <strong style="color:#4a9eff;">+</strong> suivi du prénom :<br>
        <code style="background:rgba(74,158,255,0.15); padding:3px 8px;
        border-radius:5px;">+Kamel</code><br>
        Faites-le <strong>au moins deux heure avant</strong> de lancer l'application.</p>

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
    <div class="footer">⚽ BRFOOT Generator Pro — Génération équilibrée automatique</div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
