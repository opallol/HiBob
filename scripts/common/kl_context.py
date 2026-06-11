"""
common/kl_context.py
Mengambil konteks mandat K/L dari knowledge graph (deepseek_policy_kl_assignments)
untuk di-inject ke prompt TreasurAI sebagai grounding berbasis RPJMN/RKP.
"""


def get_kl_mandate_context(cur, kl_kode, max_kp=10):
    """
    Kembalikan string konteks mandat K/L dari RPJMN/RKP.

    Format output:
        Mandat K/L 128 dalam RPJMN/RKP:
        - KP 04.12.01 [pelaksana]: Pemberian Makan Bergizi untuk Siswa... (RPJMN)
        - KP 04.12.02 [pelaksana]: Penguatan Ekosistem Pendukung... (RPJMN)

    Jika tidak ada penugasan → kembalikan string kosong.
    """
    cur.execute("""
        SELECT ka.role,
               n.node_code,
               n.node_type,
               COALESCE(n.clean_node_name_ai, n.node_name) AS kp_name,
               n.source_type
        FROM deepseek_policy_kl_assignments ka
        JOIN deepseek_policy_nodes n ON ka.node_id = n.id
        WHERE ka.kddept = %s
          AND n.node_type IN ('KP', 'PP')
        ORDER BY
            CASE n.source_type
                WHEN 'RPJMN'    THEN 1
                WHEN 'RKP_2026' THEN 2
                WHEN 'RKP_2025' THEN 3
                ELSE 4
            END,
            CASE n.node_type WHEN 'KP' THEN 1 ELSE 2 END,
            n.node_code
        LIMIT %s
    """, (kl_kode, max_kp))
    rows = cur.fetchall()

    if not rows:
        return ""

    lines = ["Mandat K/L %s dalam RPJMN/RKP:" % kl_kode]
    for role, code, ntype, name, source in rows:
        # Potong nama jika terlalu panjang
        name_short = name[:90].rstrip() + ("..." if len(name) > 90 else "")
        lines.append("  - %s %s [%s]: %s (%s)" % (ntype, code, role, name_short, source))

    return "\n".join(lines)


def get_kl_kp_codes(cur, kl_kode):
    """
    Kembalikan set kode KP yang ditugaskan ke K/L ini.
    Berguna untuk cross-check apakah output anomali ada dalam mandat eksplisit.
    """
    cur.execute("""
        SELECT n.node_code
        FROM deepseek_policy_kl_assignments ka
        JOIN deepseek_policy_nodes n ON ka.node_id = n.id
        WHERE ka.kddept = %s AND n.node_type = 'KP'
    """, (kl_kode,))
    return {r[0] for r in cur.fetchall()}
