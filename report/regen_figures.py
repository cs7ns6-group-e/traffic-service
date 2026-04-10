#!/usr/bin/env python3
"""
Two improved iterations each of:
  fig14 -- Dependency graph (more professional, white background, large text)
  fig04 -- Ghost reservation (no overlapping text)

Run: python3 report/regen_figures.py
Output: report/figures/fig04_v2_*, fig04_v3_*, fig14_v2_*, fig14_v3_*
"""

import os, math, numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch
import matplotlib.patheffects as pe

try:
    import networkx as nx
    NX = True
except ImportError:
    NX = False

OUT = os.path.join(os.path.dirname(__file__), "figures")
os.makedirs(OUT, exist_ok=True)

C = {
    "eu":        "#3B82F6",
    "us":        "#10B981",
    "apac":      "#F59E0B",
    "redis":     "#DC2626",
    "rabbit":    "#EA580C",
    "postgres":  "#7C3AED",
    "nginx":     "#475569",
    "auth":      "#4F46E5",
    "notify":    "#DB2777",
    "admin":     "#0891B2",
    "conflict":  "#B91C1C",
    "routing":   "#059669",
    "authority": "#D97706",
    "bg":        "#F8FAFC",
    "bg_dark":   "#0F172A",
    "border":    "#E2E8F0",
    "text":      "#1E293B",
    "text_light":"#FFFFFF",
    "muted":     "#64748B",
    "grid":      "#E2E8F0",
    "layer0":    "#1E3A5F",
    "layer1":    "#1B4332",
    "layer2":    "#4A1942",
}

STYLE = {
    "figure.facecolor": C["bg"],
    "axes.facecolor":   C["bg"],
    "font.family":      "sans-serif",
    "font.size":        10,
    "text.color":       C["text"],
}
plt.rcParams.update(STYLE)

def save(name, fig):
    path = os.path.join(OUT, f"{name}.png")
    fig.savefig(path, dpi=180, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"  Saved: figures/{name}.png")


# ==============================================================================
# FIG 14 V2 -- Layered Architecture Diagram (WHITE BG, report-ready, large text)
# ==============================================================================
def fig14_v2():
    """
    Three horizontal swimlanes on WHITE background -- print-ready.
      Lane 1 (top): Client + API Gateway
      Lane 2 (mid): 7 microservices
      Lane 3 (bot): Infrastructure + External services
    Large nodes, 11-12pt fonts, dark text -- suitable for academic reports.
    """
    fig, ax = plt.subplots(figsize=(28, 18))
    fig.patch.set_facecolor("#FFFFFF")
    ax.set_facecolor("#FFFFFF")
    ax.set_xlim(-0.8, 20.0)
    ax.set_ylim(-0.5, 13.0)
    ax.axis("off")

    # -- Lane backgrounds ------------------------------------------------------
    # (y_bot, y_top, fill_color, label)
    lanes = [
        (11.0, 12.8, "#DBEAFE", "CLIENT  &  GATEWAY"),
        ( 5.8, 10.8, "#DCFCE7", "MICROSERVICES"),
        (-0.2,  5.6, "#EDE9FE", "INFRASTRUCTURE  &  EXTERNAL"),
    ]
    for y_bot, y_top, color, label in lanes:
        ax.add_patch(mpatches.FancyBboxPatch(
            (-0.6, y_bot), 20.4, y_top - y_bot,
            boxstyle="round,pad=0.15", linewidth=1.5,
            edgecolor="#CBD5E1", facecolor=color, alpha=0.70, zorder=0))
        # Lane label on left side, rotated
        ax.text(-0.55, (y_bot + y_top) / 2, label,
                ha="left", va="center", fontsize=10, fontweight="bold",
                color="#475569", alpha=0.80, rotation=90)

    # -- Node definitions ------------------------------------------------------
    # (id, label, sub, x, y, color)
    nodes = [
        # lane 1 -- client + gateway
        ("client",    "Browser / App",     "React 18 + Vite",           3.5,  12.0, "#334155"),
        ("nginx",     "nginx  :80",         "Rate-limit / SPA / Proxy",  11.0, 12.0, "#475569"),
        # lane 2 -- services
        ("auth",      "auth_service",       ":8000  JWT / bcrypt",        1.5,  8.8,  "#4F46E5"),
        ("journey",   "journey_booking",    ":8001  Core engine",          5.0,  8.8,  "#2563EB"),
        ("conflict",  "conflict_detect",    ":8002  Slots / Locks",        8.5,  8.8,  "#DC2626"),
        ("routing",   "road_routing",       ":8004  OSRM / Nominatim",    12.5,  8.8,  "#059669"),
        ("authority", "traffic_authority",  ":8005  Closures",            16.0,  7.6,  "#D97706"),
        ("admin",     "admin_service",      ":8006  Observability",       18.5,  8.8,  "#0891B2"),
        ("notify",    "notification",       ":8003  Events / Telegram",    5.0,  6.9,  "#DB2777"),
        # lane 3 -- infra
        ("postgres",  "PostgreSQL 15",      "Per-region ACID store",       4.0,  3.6,  "#7C3AED"),
        ("redis",     "Redis 7",            "Locks / Cache / TTL",         9.5,  3.6,  "#DC2626"),
        ("rabbit",    "RabbitMQ 3",         "Federation / 6 queues",      15.5,  3.6,  "#EA580C"),
        ("osrm",      "OSRM  (ext)",        "Routing engine",             12.5,  1.3,  "#334155"),
        ("nominatim", "Nominatim  (ext)",   "Geocoding API",              17.0,  1.3,  "#334155"),
        ("telegram",  "Telegram  (ext)",    "Push notifications",           1.5,  1.3,  "#334155"),
    ]

    node_pos = {}
    node_w, node_h = 3.2, 1.10

    for nid, label, sub, x, y, color in nodes:
        node_pos[nid] = (x, y)
        box = FancyBboxPatch((x - node_w/2, y - node_h/2), node_w, node_h,
                              boxstyle="round,pad=0.09", linewidth=2.2,
                              edgecolor=color, facecolor=color + "15", zorder=3)
        ax.add_patch(box)
        ax.text(x, y + 0.20, label, ha="center", va="center",
                fontsize=11, fontweight="bold", color="#0F172A", zorder=4)
        ax.text(x, y - 0.28, sub, ha="center", va="center",
                fontsize=8.5, color=color, alpha=0.95, zorder=4)

    # -- Edges -----------------------------------------------------------------
    edges = [
        # (src, dst, label, color, style)
        ("client",    "nginx",     "HTTPS",               "#64748B", "solid"),
        ("nginx",     "auth",      "/auth/*",             "#4F46E5", "solid"),
        ("nginx",     "journey",   "/journeys",           "#2563EB", "solid"),
        ("nginx",     "conflict",  "/conflicts/*",        "#DC2626", "solid"),
        ("nginx",     "routing",   "/route  /search",     "#059669", "solid"),
        ("nginx",     "authority", "/authority/*",        "#D97706", "solid"),
        ("nginx",     "admin",     "/admin/*",            "#0891B2", "solid"),
        ("journey",   "conflict",  "POST /check",         "#DC2626", "dashed"),
        ("journey",   "routing",   "POST /route",         "#059669", "dashed"),
        ("journey",   "notify",    "booking_events",      "#DB2777", "dotted"),
        ("authority", "notify",    "closure_events",      "#DB2777", "dotted"),
        ("journey",   "postgres",  "INSERT/SELECT",       "#7C3AED", "solid"),
        ("auth",      "postgres",  "users/tokens",        "#7C3AED", "solid"),
        ("authority", "postgres",  "closures/journeys",   "#7C3AED", "solid"),
        ("admin",     "postgres",  "stats",               "#7C3AED", "solid"),
        ("conflict",  "redis",     "SETEX/GET locks",     "#DC2626", "solid"),
        ("routing",   "redis",     "SETEX geocache",      "#DC2626", "solid"),
        ("admin",     "redis",     "INFO",                "#DC2626", "dashed"),
        ("notify",    "rabbit",    "consume x6 queues",   "#EA580C", "solid"),
        ("journey",   "rabbit",    "publish events",      "#EA580C", "solid"),
        ("authority", "rabbit",    "publish events",      "#EA580C", "solid"),
        ("admin",     "rabbit",    "HTTP mgmt API",       "#EA580C", "dashed"),
        ("notify",    "postgres",  "replicated_journeys", "#7C3AED", "solid"),
        ("routing",   "osrm",      "GET /route",          "#475569", "dashed"),
        ("routing",   "nominatim", "GET ?q=",             "#475569", "dashed"),
        ("notify",    "telegram",  "sendMessage",         "#475569", "dashed"),
    ]

    style_map = {"solid": (1.8, []), "dashed": (1.3, [6, 3]), "dotted": (1.1, [2, 2])}

    for src, dst, label, color, style in edges:
        if src not in node_pos or dst not in node_pos:
            continue
        x1, y1 = node_pos[src]
        x2, y2 = node_pos[dst]
        lw, dash = style_map[style]
        ax.annotate("",
            xy=(x2, y2 + node_h/2 * (1 if y2 < y1 else -1)),
            xytext=(x1, y1 - node_h/2 * (1 if y2 < y1 else -1)),
            arrowprops=dict(
                arrowstyle="-|>",
                color=color,
                lw=lw,
                alpha=0.82,
                linestyle=(0, dash) if dash else "solid",
                connectionstyle="arc3,rad=0.07",
            ), zorder=2)
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        if label:
            ax.text(mx, my + 0.08, label, ha="center", va="bottom",
                    fontsize=7.5, color=color, alpha=0.95, zorder=5,
                    bbox=dict(boxstyle="round,pad=0.12", facecolor="#FFFFFF",
                              edgecolor=color + "88", alpha=0.95, linewidth=0.8))

    # -- Legend ----------------------------------------------------------------
    legend_items = [
        (mpatches.Patch(facecolor="#4F46E5"+"15", edgecolor="#4F46E5", linewidth=2), "Auth Service"),
        (mpatches.Patch(facecolor="#2563EB"+"15", edgecolor="#2563EB", linewidth=2), "Journey Booking"),
        (mpatches.Patch(facecolor="#DC2626"+"15", edgecolor="#DC2626", linewidth=2), "Conflict Detection"),
        (mpatches.Patch(facecolor="#059669"+"15", edgecolor="#059669", linewidth=2), "Road Routing"),
        (mpatches.Patch(facecolor="#7C3AED"+"15", edgecolor="#7C3AED", linewidth=2), "PostgreSQL"),
        (mpatches.Patch(facecolor="#DC2626"+"15", edgecolor="#DC2626", linewidth=2), "Redis"),
        (mpatches.Patch(facecolor="#EA580C"+"15", edgecolor="#EA580C", linewidth=2), "RabbitMQ"),
        (plt.Line2D([0],[0], color="#64748B", lw=2.0),                               "HTTP request"),
        (plt.Line2D([0],[0], color="#DB2777", lw=1.3, linestyle=(0,[6,3])),          "Async event (RabbitMQ)"),
        (plt.Line2D([0],[0], color="#475569", lw=1.1, linestyle=(0,[2,2])),          "External API call"),
    ]
    handles, labels = zip(*legend_items)
    ax.legend(handles, labels, loc="lower left", fontsize=9.5,
              framealpha=1.0, facecolor="#F8FAFC", edgecolor="#CBD5E1",
              labelcolor="#1E293B", ncol=2, handlelength=2.4,
              borderpad=0.9, labelspacing=0.65)

    ax.set_title("TrafficBook -- Microservice Dependency Graph",
                 fontsize=20, fontweight="bold", color="#0F172A", pad=18)

    save("fig14_v2_dependency_layered", fig)


# ==============================================================================
# FIG 14 V3 -- Radial / Hub-and-Spoke (WHITE BG, report-ready, large text)
# ==============================================================================
def fig14_v3():
    """
    nginx at centre on WHITE background -- print-ready.
    Inner ring: 7 microservices.
    Outer ring: infrastructure + external services.
    Large nodes (r=0.90 for services, r=0.72 for infra), 11-13pt fonts.
    """
    fig, ax = plt.subplots(figsize=(22, 22))
    fig.patch.set_facecolor("#FFFFFF")
    ax.set_facecolor("#FFFFFF")
    ax.set_xlim(-7.8, 7.8)
    ax.set_ylim(-7.8, 7.8)
    ax.axis("off")
    ax.set_aspect("equal")

    # Subtle guide rings on white bg
    for r, alpha in [(2.0, 0.07), (4.0, 0.06), (6.2, 0.05)]:
        circle = plt.Circle((0, 0), r, color="#94A3B8", fill=False,
                             linewidth=0.8, alpha=alpha)
        ax.add_patch(circle)

    # -- Node placement --------------------------------------------------------
    services = [
        ("auth",      "auth_service\n:8000",      "#4F46E5"),
        ("journey",   "journey_booking\n:8001",    "#2563EB"),
        ("conflict",  "conflict_detect\n:8002",    "#DC2626"),
        ("notify",    "notification\n:8003",       "#DB2777"),
        ("routing",   "road_routing\n:8004",       "#059669"),
        ("authority", "traffic_authority\n:8005",  "#D97706"),
        ("admin",     "admin_service\n:8006",      "#0891B2"),
    ]
    infra = [
        ("postgres",  "PostgreSQL",         "#7C3AED"),
        ("redis",     "Redis",              "#DC2626"),
        ("rabbit",    "RabbitMQ",           "#EA580C"),
        ("osrm",      "OSRM",              "#475569"),
        ("nominatim", "Nominatim",         "#475569"),
        ("telegram",  "Telegram",          "#475569"),
        ("client",    "Browser\n(React)",  "#334155"),
        ("grafana",   "Grafana /\nPrometheus", "#F97316"),
    ]

    n_svc = len(services)
    n_inf = len(infra)
    R_svc = 3.5
    R_inf = 6.3
    pos = {}

    # nginx at centre
    pos["nginx"] = (0, 0)

    # Services evenly spaced on inner ring
    for i, (nid, _, _) in enumerate(services):
        angle = math.pi / 2 + i * (2 * math.pi / n_svc)
        pos[nid] = (R_svc * math.cos(angle), R_svc * math.sin(angle))

    # Infra on outer ring
    for i, (nid, _, _) in enumerate(infra):
        angle = math.pi / 2 + i * (2 * math.pi / n_inf)
        pos[nid] = (R_inf * math.cos(angle), R_inf * math.sin(angle))

    def draw_node(nid, label, color, radius=0.72, fontsize=10):
        x, y = pos[nid]
        # Outer ring (border)
        border = plt.Circle((x, y), radius + 0.06, color=color, alpha=0.30,
                             linewidth=0, zorder=2)
        ax.add_patch(border)
        # Main circle with light fill
        circle = plt.Circle((x, y), radius, color=color, alpha=0.15,
                             linewidth=2.5, zorder=3)
        ax.add_patch(circle)
        # Strong colored border
        ring = plt.Circle((x, y), radius, color=color, fill=False,
                          linewidth=2.5, zorder=4)
        ax.add_patch(ring)
        ax.text(x, y, label, ha="center", va="center",
                fontsize=fontsize, fontweight="bold", color="#0F172A",
                zorder=5, linespacing=1.35)

    # Draw nginx hub (largest node)
    x0, y0 = pos["nginx"]
    hub_border = plt.Circle((x0, y0), 1.10, color="#475569", alpha=0.20, zorder=2)
    ax.add_patch(hub_border)
    hub = plt.Circle((x0, y0), 1.00, color="#475569", alpha=0.12,
                     linewidth=0, zorder=3)
    ax.add_patch(hub)
    hub_ring = plt.Circle((x0, y0), 1.00, color="#475569", fill=False,
                          linewidth=3.0, zorder=4)
    ax.add_patch(hub_ring)
    ax.text(x0, y0 + 0.18, "nginx", ha="center", va="center",
            fontsize=16, fontweight="bold", color="#0F172A", zorder=5)
    ax.text(x0, y0 - 0.32, ":80  Gateway", ha="center", va="center",
            fontsize=10, color="#475569", zorder=5)

    for nid, label, color in services:
        draw_node(nid, label, color, radius=0.90, fontsize=11)

    for nid, label, color in infra:
        draw_node(nid, label, color, radius=0.72, fontsize=9.5)

    # -- Edges -----------------------------------------------------------------
    def arrow(src, dst, color, lw=1.2, rad=0.15, dash=None, alpha=0.65):
        x1, y1 = pos[src]
        x2, y2 = pos[dst]
        dx, dy = x2 - x1, y2 - y1
        d = math.sqrt(dx**2 + dy**2)
        if d == 0:
            return
        svc_ids = {nid for nid, _, _ in services}
        r1 = 1.00 if src == "nginx" else (0.90 if src in svc_ids else 0.72)
        r2 = 1.00 if dst == "nginx" else (0.90 if dst in svc_ids else 0.72)
        fx1 = x1 + dx / d * r1
        fy1 = y1 + dy / d * r1
        fx2 = x2 - dx / d * r2
        fy2 = y2 - dy / d * r2
        ls = (0, dash) if dash else "solid"
        ax.annotate("", xy=(fx2, fy2), xytext=(fx1, fy1),
                    arrowprops=dict(
                        arrowstyle="-|>",
                        color=color,
                        lw=lw,
                        alpha=alpha,
                        linestyle=ls,
                        connectionstyle=f"arc3,rad={rad}",
                    ), zorder=4)

    # nginx -> services
    for nid, _, color in services:
        arrow("nginx", nid, color, lw=1.8, rad=0.0, alpha=0.55)

    # client -> nginx
    arrow("client", "nginx", "#64748B", lw=2.0, rad=0.15, alpha=0.75)

    # Service -> infra edges
    svc_infra = [
        ("journey",   "postgres",   "#7C3AED", 1.4),
        ("auth",      "postgres",   "#7C3AED", 1.2),
        ("authority", "postgres",   "#7C3AED", 1.2),
        ("admin",     "postgres",   "#7C3AED", 1.0),
        ("notify",    "postgres",   "#7C3AED", 1.0),
        ("conflict",  "redis",      "#DC2626", 1.4),
        ("routing",   "redis",      "#DC2626", 1.2),
        ("admin",     "redis",      "#DC2626", 0.9),
        ("journey",   "rabbit",     "#EA580C", 1.4),
        ("authority", "rabbit",     "#EA580C", 1.2),
        ("notify",    "rabbit",     "#EA580C", 1.5),
        ("admin",     "rabbit",     "#EA580C", 0.9),
        ("routing",   "osrm",       "#475569", 1.1),
        ("routing",   "nominatim",  "#475569", 1.1),
        ("notify",    "telegram",   "#475569", 1.2),
        ("admin",     "grafana",    "#F97316", 1.0),
    ]
    for src, dst, color, lw in svc_infra:
        arrow(src, dst, color, lw=lw, rad=0.20, dash=[5,3], alpha=0.60)

    # service->service
    svc_svc = [
        ("journey",  "conflict",   "#DC2626", 1.1),
        ("journey",  "routing",    "#059669", 1.1),
        ("journey",  "notify",     "#DB2777", 0.9),
        ("authority","notify",     "#DB2777", 0.9),
    ]
    for src, dst, color, lw in svc_svc:
        arrow(src, dst, color, lw=lw, rad=0.40, alpha=0.70)

    # -- Route labels on inner ring (between nginx and services) ---------------
    def ring_label(text, angle_deg, r=2.0, fontsize=8.0):
        rad = math.radians(angle_deg)
        x = r * math.cos(rad)
        y = r * math.sin(rad)
        ax.text(x, y, text, ha="center", va="center", fontsize=fontsize,
                color="#334155", alpha=0.85,
                bbox=dict(boxstyle="round,pad=0.14", facecolor="#F1F5F9",
                          edgecolor="#CBD5E1", alpha=0.90, linewidth=0.7))

    svc_routes = {
        "auth":      "/auth/*",
        "journey":   "/journeys",
        "conflict":  "/conflicts/*",
        "notify":    "(consumer)",
        "routing":   "/route\n/search",
        "authority": "/authority/*",
        "admin":     "/admin/*",
    }
    for i, (nid, _, _) in enumerate(services):
        angle = 90 + i * (360 / n_svc)
        ring_label(svc_routes.get(nid, ""), angle, r=2.05)

    # -- Legend ----------------------------------------------------------------
    legend = [
        (plt.Line2D([0],[0], color="#475569", lw=2.0),                              "nginx -> service (HTTP proxy)"),
        (plt.Line2D([0],[0], color="#7C3AED", lw=1.4, linestyle=(0,[5,3])),         "Service -> PostgreSQL"),
        (plt.Line2D([0],[0], color="#DC2626", lw=1.4, linestyle=(0,[5,3])),         "Service -> Redis"),
        (plt.Line2D([0],[0], color="#EA580C", lw=1.4, linestyle=(0,[5,3])),         "Service -> RabbitMQ"),
        (plt.Line2D([0],[0], color="#DC2626", lw=1.1, linestyle=(0,[5,3])),         "Internal service call"),
        (plt.Line2D([0],[0], color="#475569", lw=1.0, linestyle=(0,[5,3])),         "External API"),
    ]
    handles, labels = zip(*legend)
    ax.legend(handles, labels, loc="lower right", fontsize=10, ncol=1,
              framealpha=1.0, facecolor="#F8FAFC", edgecolor="#CBD5E1",
              labelcolor="#1E293B", handlelength=2.5, borderpad=0.9)

    ax.set_title("TrafficBook -- Microservice Architecture (Radial View)",
                 fontsize=20, fontweight="bold", color="#0F172A", pad=18)

    save("fig14_v3_dependency_radial", fig)


# ==============================================================================
# FIG 04 V2 -- Ghost Reservation: Swimlane Timeline (no overlap)
# ==============================================================================
def fig04_v2():
    """
    Separate horizontal swimlane per actor.
    Events placed along a shared timeline axis.
    Labels sit exclusively in their own lane -- no cross-lane overlap.
    """
    fig, ax = plt.subplots(figsize=(18, 9))
    fig.patch.set_facecolor("#FFFFFF")
    ax.set_facecolor("#FFFFFF")
    ax.set_xlim(-1, 135)
    ax.set_ylim(-0.8, 8.5)
    ax.axis("off")

    # -- Swimlanes -------------------------------------------------------------
    LANES = {
        "User A":             7.6,
        "User B":             5.9,
        "nginx / Server":     4.2,
        "Redis":              2.5,
        "PostgreSQL":         0.8,
    }
    lane_colors = {
        "User A":         "#EFF6FF",
        "User B":         "#F0FDF4",
        "nginx / Server": "#FFF7ED",
        "Redis":          "#FFF1F2",
        "PostgreSQL":     "#F5F3FF",
    }
    lane_border = {
        "User A": "#BFDBFE", "User B": "#BBF7D0",
        "nginx / Server": "#FED7AA", "Redis": "#FECACA", "PostgreSQL": "#DDD6FE",
    }
    lane_text = {
        "User A": "#1D4ED8", "User B": "#15803D",
        "nginx / Server": "#C2410C", "Redis": "#B91C1C", "PostgreSQL": "#6D28D9",
    }

    lane_h = 1.4
    sorted_lanes = list(LANES.items())
    for name, cy in sorted_lanes:
        bot = cy - lane_h / 2
        ax.add_patch(mpatches.FancyBboxPatch(
            (-0.8, bot), 135.5, lane_h,
            boxstyle="square,pad=0", linewidth=1,
            facecolor=lane_colors[name], edgecolor=lane_border[name]))
        ax.text(-0.6, cy, name, ha="left", va="center",
                fontsize=9, fontweight="bold", color=lane_text[name])
        # lifeline
        ax.plot([5, 134], [cy, cy], color=lane_border[name], lw=1.0, zorder=1)

    # -- Event definitions -----------------------------------------------------
    # (t, lane, label_above, color, shape)
    events = [
        # User A flow
        (8,   "User A",         "Selects slot 09:00",               "#1D4ED8", "o"),
        (16,  "nginx / Server", "POST /conflicts/reserve-slot",      "#C2410C", ">"),
        (18,  "Redis",          "SETEX slot_hold:...:09:00  TTL=120s", "#B91C1C", "s"),
        (20,  "nginx / Server", "{ reserved:true, expires_in:120 }", "#C2410C", "<"),
        (22,  "User A",         "Slot shown as held (orange)",       "#1D4ED8", "o"),
        (22,  "User A",         "Filling booking form...",           "#1D4ED8", None),
        (60,  "User A",         "POST /journeys",                    "#1D4ED8", "o"),
        (62,  "nginx / Server", "-> journey_booking",                "#C2410C", ">"),
        (64,  "Redis",          "GET slot_hold (still held by A)",   "#B91C1C", "s"),
        (67,  "PostgreSQL",     "INSERT journeys -> CONFIRMED",      "#6D28D9", "D"),
        (72,  "nginx / Server", "{ status: CONFIRMED }",             "#C2410C", "<"),
        (74,  "User A",         "Journey CONFIRMED",                 "#1D4ED8", "*"),

        # User B flow
        (28,  "User B",         "Selects slot 09:00",                "#15803D", "o"),
        (30,  "nginx / Server", "POST /conflicts/slots (GET grid)",  "#C2410C", ">"),
        (32,  "Redis",          "GET slot_hold -> { driver_id: A }", "#B91C1C", "s"),
        (34,  "nginx / Server", "slot: being_selected, held_by_you:false", "#C2410C", "<"),
        (36,  "User B",         "Slot shows held by other",          "#15803D", "o"),
        (80,  "User B",         "Slot now 'booked' (A confirmed)",   "#15803D", "o"),
        (82,  "User B",         "Selects different time slot",       "#15803D", "^"),
    ]

    for item in events:
        t, lane, label, color, shape = item
        cy = LANES[lane]
        if shape:
            ms = 12 if shape == "*" else 8
            ax.plot(t, cy, shape, color=color, ms=ms, zorder=5,
                    markeredgecolor="white", markeredgewidth=0.8)

    # Label placement -- strictly within each lane's vertical space
    for item in events:
        t, lane, label, color, shape = item
        cy = LANES[lane]
        slot = round(t / 8)
        flip = (slot + list(LANES.keys()).index(lane)) % 2
        off = 0.38 if flip else -0.38
        va = "bottom" if off > 0 else "top"
        ax.text(t, cy + off, label, ha="center", va=va,
                fontsize=7.2, color=color,
                bbox=dict(boxstyle="round,pad=0.15", facecolor="white",
                          edgecolor=color + "55", alpha=0.9, linewidth=0.6))

    # -- Vertical message arrows between lanes ---------------------------------
    messages = [
        (16,  "User A",         "nginx / Server", ""),
        (16,  "nginx / Server", "Redis",          ""),
        (18,  "Redis",          "nginx / Server", ""),
        (20,  "nginx / Server", "User A",         ""),
        (30,  "User B",         "nginx / Server", ""),
        (30,  "nginx / Server", "Redis",          ""),
        (32,  "Redis",          "nginx / Server", ""),
        (34,  "nginx / Server", "User B",         ""),
        (60,  "User A",         "nginx / Server", ""),
        (62,  "nginx / Server", "Redis",          "check"),
        (64,  "Redis",          "nginx / Server", "held"),
        (62,  "nginx / Server", "PostgreSQL",     "INSERT"),
        (67,  "PostgreSQL",     "nginx / Server", "id"),
        (72,  "nginx / Server", "User A",         ""),
    ]
    for t, src, dst, lbl in messages:
        y1 = LANES[src]
        y2 = LANES[dst]
        dy = -0.70 if y2 < y1 else 0.70
        dy2 = 0.70 if y2 < y1 else -0.70
        col = lane_text[src]
        ax.annotate("", xy=(t, y2 + dy2), xytext=(t, y1 + dy),
                    arrowprops=dict(arrowstyle="-|>", color=col,
                                   lw=0.9, alpha=0.6))

    # -- Redis TTL bar ---------------------------------------------------------
    cy_redis = LANES["Redis"]
    ax.barh(cy_redis, 120, left=18, height=0.25,
            color="#B91C1C", alpha=0.25, zorder=1)
    ax.text(78, cy_redis + 0.22, "Redis TTL 120s active (slot_hold key)",
            ha="center", va="bottom", fontsize=7.5, color="#B91C1C",
            style="italic")
    ax.axvline(138, color="#B91C1C", lw=0.6, linestyle=":", alpha=0.4)

    # -- Time axis -------------------------------------------------------------
    ax.annotate("", xy=(133, -0.55), xytext=(5, -0.55),
                arrowprops=dict(arrowstyle="-|>", color="#94A3B8", lw=1.5))
    for t in range(0, 130, 10):
        ax.text(t + 5, -0.62, f"{t}s", ha="center", va="top",
                fontsize=7.5, color="#94A3B8")
        ax.plot([t + 5, t + 5], [-0.52, -0.48], color="#CBD5E1", lw=0.8)

    ax.set_title("Ghost Reservation Protocol -- Swimlane Timeline\n"
                 "Two concurrent users competing for slot 09:00",
                 fontsize=13, fontweight="bold", color="#1E293B", pad=10)

    save("fig04_v2_ghost_swimlane", fig)


# ==============================================================================
# FIG 04 V3 -- Ghost Reservation: Step-by-step annotated diagram
# ==============================================================================
def fig04_v3():
    """
    Two-column layout: User A (left), User B (right), shared server column centre.
    Numbered steps 1-12 clearly spaced vertically.
    No overlapping text -- every label has its own vertical row.
    """
    fig, ax = plt.subplots(figsize=(16, 14))
    fig.patch.set_facecolor("#FAFAFA")
    ax.set_facecolor("#FAFAFA")
    ax.set_xlim(-0.5, 16)
    ax.set_ylim(-0.5, 14.5)
    ax.axis("off")

    # Column centres
    COL = {"A": 2.0, "server": 8.0, "redis": 11.5, "pg": 14.5, "B": 5.5}

    # Draw actor headers
    actor_defs = [
        ("A",      "User A",          "#1D4ED8"),
        ("B",      "User B",          "#15803D"),
        ("server", "nginx / journey\nrouting / conflict", "#C2410C"),
        ("redis",  "Redis",           "#B91C1C"),
        ("pg",     "PostgreSQL",      "#6D28D9"),
    ]
    for key, label, color in actor_defs:
        x = COL[key]
        ax.add_patch(FancyBboxPatch((x - 1.1, 13.3), 2.2, 0.9,
                                    boxstyle="round,pad=0.08", linewidth=1.5,
                                    facecolor=color + "20", edgecolor=color))
        ax.text(x, 13.75, label, ha="center", va="center",
                fontsize=8.5, fontweight="bold", color=color, linespacing=1.3)
        ax.plot([x, x], [-0.3, 13.3], color=color, lw=0.7,
                linestyle="--", alpha=0.25, zorder=0)

    # Step rows -- each step occupies its own y row with 1.1 unit spacing
    STEP_H = 1.15
    steps = [
        (1,  12.0, "A",      "server", "->", "Selects slot 09:00\n(clicks SlotGrid)",
                                             "Browser calls\nPOST /conflicts/reserve-slot",   "#1D4ED8", "#C2410C"),
        (2,  10.8, "server", "redis",  "->", "SETEX slot_hold:Dublin:Cork:09:00",
                                             "TTL = 120 s\n{driver_id: 'A', reserved_at: ...}", "#C2410C", "#B91C1C"),
        (3,   9.6, "redis",  "server", "<-", "OK",
                                             "{reserved:true, expires_in:120}",                "#B91C1C", "#C2410C"),
        (4,   8.4, "server", "A",      "<-", "Response to User A",
                                             "Slot turns orange -> 'Held by you'",              "#C2410C", "#1D4ED8"),
        (5,   7.2, "B",      "server", "->", "User B selects same slot",
                                             "GET /conflicts/slots",                            "#15803D", "#C2410C"),
        (6,   6.0, "server", "redis",  "->", "GET slot_hold:Dublin:Cork:09:00",
                                             "",                                                "#C2410C", "#B91C1C"),
        (7,   4.8, "redis",  "server", "<-", "{driver_id:'A', reserved_at:...}",
                                             "Key exists -> held by A",                         "#B91C1C", "#C2410C"),
        (8,   3.6, "server", "B",      "<-", "slot: being_selected\nheld_by_you: false",
                                             "Slot shows grey (unavailable)",                  "#C2410C", "#15803D"),
        (9,   2.4, "A",      "server", "->", "POST /journeys\n{origin, dest, start_time}",
                                             "Conflict check -> Redis key cleared\nINSERT journeys", "#1D4ED8", "#C2410C"),
        (10,  2.4, "server", "pg",     "->", "INSERT INTO journeys",
                                             "",                                                "#C2410C", "#6D28D9"),
        (11,  1.2, "pg",     "server", "<-", "{ status: CONFIRMED }",
                                             "",                                                "#6D28D9", "#C2410C"),
        (12,  0.0, "server", "A",      "<-", "Journey CONFIRMED",
                                             "User B will see slot 'booked'\nnext time they load",   "#C2410C", "#1D4ED8"),
    ]

    for step_no, y, src, dst, _, lbl_left, lbl_right, c_src, c_dst in steps:
        x1 = COL[src]
        x2 = COL[dst]
        mid = (x1 + x2) / 2

        # Step badge
        ax.add_patch(plt.Circle((mid, y + 0.05), 0.22,
                                facecolor=c_src, alpha=0.85, zorder=5))
        ax.text(mid, y + 0.05, str(step_no), ha="center", va="center",
                fontsize=7.5, fontweight="bold", color="white", zorder=6)

        # Arrow
        ax.annotate("", xy=(x2, y), xytext=(x1, y),
                    arrowprops=dict(arrowstyle="-|>", color=c_src,
                                   lw=1.6, alpha=0.7,
                                   connectionstyle="arc3,rad=0.0"))

        # Left label (near src)
        x_lbl_l = min(x1, x2) - 0.2
        ax.text(x_lbl_l, y + 0.32, lbl_left,
                ha="right", va="bottom", fontsize=7.2, color=c_src,
                bbox=dict(boxstyle="round,pad=0.2", facecolor="white",
                          edgecolor=c_src + "44", alpha=0.9, lw=0.7))

        # Right label (near dst)
        if lbl_right:
            x_lbl_r = max(x1, x2) + 0.2
            ax.text(x_lbl_r, y + 0.32, lbl_right,
                    ha="left", va="bottom", fontsize=7.2, color=c_dst,
                    bbox=dict(boxstyle="round,pad=0.2", facecolor="white",
                              edgecolor=c_dst + "44", alpha=0.9, lw=0.7))

    # Highlight Redis TTL window
    ax.add_patch(mpatches.FancyBboxPatch(
        (10.3, -0.35), 2.4, 12.55,
        boxstyle="square,pad=0", linewidth=1.5,
        facecolor="#B91C1C", alpha=0.05, edgecolor="#B91C1C",
        linestyle="--", zorder=0))
    ax.text(11.5, 12.35, "Redis TTL\n120 s window", ha="center",
            fontsize=7.5, color="#B91C1C", style="italic", alpha=0.7)

    # Title & subtitle
    ax.set_title("Ghost Reservation Protocol -- Step-by-Step\n"
                 "Optimistic slot locking via Redis TTL prevents double-booking",
                 fontsize=13, fontweight="bold", color="#1E293B", pad=10)

    save("fig04_v3_ghost_steps", fig)


# ==============================================================================
# FIG 05 V2 -- Replication Timeline: Swimlane (no overlap, white bg)
# ==============================================================================
def fig05_v2():
    """
    Four horizontal swimlanes: EU / US / RabbitMQ / APAC.
    Events spread over 0-30s axis -- no label collisions.
    White background, dark text, report-ready.
    """
    fig, ax = plt.subplots(figsize=(20, 10))
    fig.patch.set_facecolor("#FFFFFF")
    ax.set_facecolor("#FFFFFF")
    ax.set_xlim(-2, 32)
    ax.set_ylim(-1.0, 9.5)
    ax.axis("off")

    LANES = {
        "EU  (origin)": 8.0,
        "US":           5.8,
        "RabbitMQ":     3.6,
        "APAC":         1.4,
    }
    lane_colors  = {"EU  (origin)": "#EFF6FF", "US": "#F0FDF4",
                    "RabbitMQ": "#FFF7ED", "APAC": "#FFFBEB"}
    lane_borders = {"EU  (origin)": "#BFDBFE", "US": "#BBF7D0",
                    "RabbitMQ": "#FED7AA", "APAC": "#FDE68A"}
    lane_text    = {"EU  (origin)": "#1D4ED8", "US": "#15803D",
                    "RabbitMQ": "#C2410C", "APAC": "#B45309"}

    lane_h = 1.7
    for name, cy in LANES.items():
        ax.add_patch(mpatches.FancyBboxPatch(
            (-1.8, cy - lane_h/2), 33.5, lane_h,
            boxstyle="square,pad=0", linewidth=1.2,
            facecolor=lane_colors[name], edgecolor=lane_borders[name]))
        ax.text(-1.6, cy, name, ha="left", va="center",
                fontsize=10, fontweight="bold", color=lane_text[name])
        ax.plot([0, 31], [cy, cy], color=lane_borders[name], lw=1.2, zorder=1)

    # Events: (t, lane, label, color, marker)
    events = [
        # EU lane
        ( 1.0, "EU  (origin)", "Driver books\nDublin -> Cork",      "#1D4ED8", "o"),
        ( 4.0, "EU  (origin)", "INSERT journeys\n(EU PostgreSQL)",   "#1D4ED8", "s"),
        ( 7.0, "EU  (origin)", "Publish\njourney_replication_events","#C2410C", "^"),
        (10.0, "EU  (origin)", "HTTP POST\n-> US :8001\n(direct)",   "#1D4ED8", ">"),
        # US lane
        (12.5, "US",           "Receive HTTP POST\nfrom EU",         "#15803D", "v"),
        (15.0, "US",           "INSERT journeys\n(cross-region PG)", "#15803D", "s"),
        (17.5, "US",           "Publish\nreplication_events\n-> APAC","#C2410C","^"),
        # RabbitMQ lane
        ( 7.5, "RabbitMQ",     "EU event\nenqueued",                 "#C2410C", "D"),
        (18.5, "RabbitMQ",     "Federation\npropagates\nEU->APAC",   "#C2410C", "D"),
        (19.5, "RabbitMQ",     "US event\nenqueued\n-> APAC",        "#C2410C", "D"),
        # APAC lane
        (22.0, "APAC",         "on_replication\ncallback triggered", "#B45309", "v"),
        (25.0, "APAC",         "INSERT\nreplicated_journeys\n(APAC PG)","#B45309","s"),
        (28.5, "APAC",         "State converged\n(eventual consistency)","#B45309","*"),
    ]

    # Place events with alternating label positions per lane
    lane_slot_counters = {k: 0 for k in LANES}
    for t, lane, label, color, marker in events:
        cy = LANES[lane]
        ms = 14 if marker == "*" else 10
        ax.plot(t, cy, marker, color=color, ms=ms, zorder=5,
                markeredgecolor="white", markeredgewidth=1.0)
        # Alternate above/below within lane
        idx = lane_slot_counters[lane]
        lane_slot_counters[lane] += 1
        off = 0.52 if idx % 2 == 0 else -0.52
        va  = "bottom" if off > 0 else "top"
        ax.text(t, cy + off, label, ha="center", va=va,
                fontsize=7.8, color=color,
                bbox=dict(boxstyle="round,pad=0.18", facecolor="#FFFFFF",
                          edgecolor=color + "66", alpha=0.95, linewidth=0.7))

    # Cross-lane arrows
    arrow_defs = [
        # (t, from_lane, to_lane, label)
        ( 7.2, "EU  (origin)", "RabbitMQ",   "publish"),
        (10.2, "EU  (origin)", "US",          "HTTP"),
        (18.0, "RabbitMQ",     "APAC",        "federation"),
        (17.8, "US",           "RabbitMQ",    "publish"),
        (19.8, "RabbitMQ",     "APAC",        "enqueue"),
    ]
    for t, src, dst, lbl in arrow_defs:
        y1 = LANES[src]
        y2 = LANES[dst]
        gap = 0.85 if y2 < y1 else -0.85
        col = lane_text[src]
        ax.annotate("", xy=(t, y2 - gap), xytext=(t, y1 + gap),
                    arrowprops=dict(arrowstyle="-|>", color=col,
                                   lw=1.1, alpha=0.65,
                                   connectionstyle="arc3,rad=0.0"))

    # Replication lag annotation
    ax.annotate("", xy=(22.0, LANES["APAC"]), xytext=(7.0, LANES["EU  (origin)"]),
                arrowprops=dict(arrowstyle="-|>", color="#94A3B8",
                               lw=1.2, linestyle="dashed",
                               connectionstyle="arc3,rad=0.25"))
    ax.text(15.5, 5.2, "Replication lag  ~2-5 s\n(tunable via federation policy)",
            ha="center", fontsize=8.5, color="#64748B", style="italic",
            bbox=dict(boxstyle="round,pad=0.2", facecolor="#F8FAFC",
                      edgecolor="#CBD5E1", alpha=0.9))

    # Time axis
    ax.annotate("", xy=(31, -0.72), xytext=(0, -0.72),
                arrowprops=dict(arrowstyle="-|>", color="#94A3B8", lw=1.5))
    for t in range(0, 31, 5):
        ax.text(t, -0.80, f"{t}s", ha="center", va="top",
                fontsize=8, color="#94A3B8")
        ax.plot([t, t], [-0.68, -0.64], color="#CBD5E1", lw=0.9)

    ax.set_title("Eventual Consistency via RabbitMQ Federation -- Replication Timeline\n"
                 "EU origin -> direct HTTP to US -> Federation broadcast to APAC",
                 fontsize=14, fontweight="bold", color="#0F172A", pad=14)

    save("fig05_v2_replication_swimlane", fig)


# ==============================================================================
# FIG 05 V3 -- Replication Timeline: Step-by-step annotated (no overlap)
# ==============================================================================
def fig05_v3():
    """
    Vertical step-by-step diagram showing each replication hop.
    Columns: EU | RabbitMQ | US | APAC
    Each step on its own row -- zero label overlap.
    White background, dark text, report-ready.
    """
    fig, ax = plt.subplots(figsize=(18, 16))
    fig.patch.set_facecolor("#FFFFFF")
    ax.set_facecolor("#FFFFFF")
    ax.set_xlim(-0.5, 18)
    ax.set_ylim(-0.8, 17.0)
    ax.axis("off")

    COL = {"EU": 3.0, "RabbitMQ": 7.5, "US": 12.0, "APAC": 16.5}
    COL_COLOR = {
        "EU":       "#1D4ED8",
        "RabbitMQ": "#C2410C",
        "US":       "#15803D",
        "APAC":     "#B45309",
    }

    # Actor header boxes
    for name, x in COL.items():
        color = COL_COLOR[name]
        ax.add_patch(FancyBboxPatch((x - 1.6, 15.8), 3.2, 1.0,
                                    boxstyle="round,pad=0.1", linewidth=2.0,
                                    facecolor=color + "18", edgecolor=color))
        ax.text(x, 16.3, name, ha="center", va="center",
                fontsize=13, fontweight="bold", color=color)
        ax.plot([x, x], [-0.5, 15.8], color=color, lw=0.8,
                linestyle="--", alpha=0.20, zorder=0)

    # Steps: (step_no, y, src, dst, lbl_src, lbl_dst)
    steps = [
        (1,  14.5, "EU",       "EU",       "Driver completes booking\n(React form submitted)",
                                            "POST /journeys -> journey_booking :8001", "#1D4ED8", "#1D4ED8"),
        (2,  13.0, "EU",       "EU",       "Conflict check passes\nINSERT INTO journeys",
                                            "status = CONFIRMED\nid = 7841",           "#1D4ED8", "#1D4ED8"),
        (3,  11.5, "EU",       "RabbitMQ", "asyncio.create_task\npublish_event()",
                                            "journey_replication_events\n{id, origin, dest, driver_id}", "#1D4ED8", "#C2410C"),
        (4,  10.0, "EU",       "US",       "HTTP POST /journeys\n(cross-region direct call)",
                                            "Received by journey_booking :8001 (US)",   "#1D4ED8", "#15803D"),
        (5,   8.5, "US",       "US",       "INSERT INTO journeys\nON CONFLICT DO UPDATE",
                                            "Idempotent upsert\nstatus = CONFIRMED",    "#15803D", "#15803D"),
        (6,   7.0, "US",       "RabbitMQ", "Publish replication_events\n(for APAC fan-out)",
                                            "journey_replication_events\nenqueued",      "#15803D", "#C2410C"),
        (7,   5.5, "RabbitMQ", "APAC",     "Federation link\npropagates event",
                                            "on_message callback\ntriggered (APAC)",    "#C2410C", "#B45309"),
        (8,   4.0, "APAC",     "APAC",     "Parse payload\nvalidate driver_id",
                                            "INSERT INTO replicated_journeys\nON CONFLICT DO UPDATE", "#B45309", "#B45309"),
        (9,   2.5, "RabbitMQ", "US",       "Federation also delivers\nto US consumer",
                                            "on_message callback (US)\nidempotent upsert", "#C2410C", "#15803D"),
        (10,  1.0, "APAC",     "APAC",     "All regions consistent\n(eventual consistency achieved)",
                                            "BASE: eventually consistent\nacross EU / US / APAC", "#B45309", "#B45309"),
    ]

    for step_no, y, src, dst, lbl_l, lbl_r, c_src, c_dst in steps:
        x1 = COL[src]
        x2 = COL[dst]
        same = (src == dst)

        if same:
            # Self-referential: draw a small loopback arc
            ax.annotate("", xy=(x1 + 0.5, y - 0.25), xytext=(x1 - 0.5, y - 0.25),
                        arrowprops=dict(arrowstyle="-|>", color=c_src,
                                       lw=1.6, alpha=0.75,
                                       connectionstyle="arc3,rad=-0.4"))
        else:
            ax.annotate("", xy=(x2, y), xytext=(x1, y),
                        arrowprops=dict(arrowstyle="-|>", color=c_src,
                                       lw=1.8, alpha=0.75,
                                       connectionstyle="arc3,rad=0.0"))

        # Step badge at midpoint
        mid_x = (x1 + x2) / 2 if not same else x1
        ax.add_patch(plt.Circle((mid_x, y + 0.12), 0.28,
                                facecolor=c_src, alpha=0.88, zorder=5))
        ax.text(mid_x, y + 0.12, str(step_no), ha="center", va="center",
                fontsize=9, fontweight="bold", color="white", zorder=6)

        # Left label
        x_lbl_l = min(x1, x2) - 0.35 if not same else x1 - 0.6
        ax.text(x_lbl_l, y + 0.42, lbl_l, ha="right", va="bottom",
                fontsize=8, color=c_src,
                bbox=dict(boxstyle="round,pad=0.22", facecolor="#FFFFFF",
                          edgecolor=c_src + "55", alpha=0.95, lw=0.8))

        # Right label
        if lbl_r:
            x_lbl_r = max(x1, x2) + 0.35 if not same else x1 + 0.6
            ax.text(x_lbl_r, y + 0.42, lbl_r, ha="left", va="bottom",
                    fontsize=8, color=c_dst,
                    bbox=dict(boxstyle="round,pad=0.22", facecolor="#FFFFFF",
                              edgecolor=c_dst + "55", alpha=0.95, lw=0.8))

    # Lag annotation
    ax.annotate("", xy=(COL["APAC"], 4.0), xytext=(COL["EU"], 11.5),
                arrowprops=dict(arrowstyle="-|>", color="#94A3B8",
                               lw=1.0, linestyle="dashed",
                               connectionstyle="arc3,rad=0.3"))
    ax.text(10.5, 8.2, "Replication lag\n~2-5 s end-to-end",
            ha="center", fontsize=9, color="#64748B", style="italic",
            bbox=dict(boxstyle="round,pad=0.2", facecolor="#F8FAFC",
                      edgecolor="#CBD5E1", alpha=0.9))

    ax.set_title("Eventual Consistency -- Replication Step-by-Step\n"
                 "EU origin -> direct HTTP to US -> RabbitMQ federation to APAC",
                 fontsize=16, fontweight="bold", color="#0F172A", pad=16)

    save("fig05_v3_replication_steps", fig)


# -- Run -----------------------------------------------------------------------
if __name__ == "__main__":
    print("\nGenerating 6 revised figures...\n")
    fig14_v2()
    fig14_v3()
    fig04_v2()
    fig04_v3()
    fig05_v2()
    fig05_v3()
    print("\nDone.")
