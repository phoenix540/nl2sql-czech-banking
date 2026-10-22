-- Vues analytiques : couche "métier" interrogée par le moteur NL-to-SQL.
-- Les jointures et calculs sont faits ici, une fois, plutôt que devinés par le LLM.

DROP VIEW IF EXISTS v_recouvrement_par_secteur CASCADE;
DROP VIEW IF EXISTS v_ca_par_client CASCADE;
DROP VIEW IF EXISTS v_ca_mensuel CASCADE;
DROP VIEW IF EXISTS v_encaissements_mensuels_banque CASCADE;
DROP VIEW IF EXISTS v_factures_detail CASCADE;
DROP VIEW IF EXISTS v_encaissements_detail CASCADE;

-- 1. Encaissements enrichis (banque, client, secteur...) : 1 ligne = 1 encaissement
CREATE VIEW v_encaissements_detail AS
SELECT
    e.encaissement_id,
    e.date_encaissement,
    date_trunc('month', e.date_encaissement)::date  AS mois,
    EXTRACT(YEAR FROM e.date_encaissement)::int     AS annee,
    COALESCE(b.nom_banque, 'Banque inconnue')       AS nom_banque,
    e.mode_paiement,
    e.montant,
    f.facture_id,
    c.client_id,
    c.raison_sociale AS client,
    c.secteur,
    c.segment,
    c.ville
FROM encaissements e
JOIN factures f      ON f.facture_id = e.facture_id
JOIN clients  c      ON c.client_id  = f.client_id
LEFT JOIN banques b  ON b.banque_id  = e.banque_id;

-- 2. Factures enrichies avec ce qui a été encaissé et le retard
CREATE VIEW v_factures_detail AS
SELECT
    f.facture_id,
    f.client_id,
    c.raison_sociale AS client,
    c.secteur,
    c.segment,
    c.ville,
    f.date_emission,
    date_trunc('month', f.date_emission)::date AS mois_emission,
    f.date_echeance,
    f.montant_ht,
    f.montant_tva,
    f.montant_ttc,
    f.statut,
    COALESCE(p.total_encaisse, 0)                                    AS total_encaisse,
    GREATEST(f.montant_ttc - COALESCE(p.total_encaisse, 0), 0)       AS reste_a_payer,
    (f.statut <> 'Payée' AND f.date_echeance < CURRENT_DATE)         AS en_retard,
    CASE WHEN f.statut <> 'Payée' AND f.date_echeance < CURRENT_DATE
         THEN CURRENT_DATE - f.date_echeance END                     AS jours_retard
FROM factures f
JOIN clients c ON c.client_id = f.client_id
LEFT JOIN (SELECT facture_id, SUM(montant) AS total_encaisse
           FROM encaissements GROUP BY facture_id) p ON p.facture_id = f.facture_id;

-- 3. Encaissements par mois et par banque
CREATE VIEW v_encaissements_mensuels_banque AS
SELECT
    mois,
    nom_banque,
    COUNT(*)                 AS nb_encaissements,
    ROUND(SUM(montant), 3)   AS montant_total
FROM v_encaissements_detail
GROUP BY mois, nom_banque;

-- 4. Chiffre d'affaires facturé par mois
CREATE VIEW v_ca_mensuel AS
SELECT
    mois_emission AS mois,
    COUNT(*)                      AS nb_factures,
    ROUND(SUM(montant_ht), 3)     AS ca_ht,
    ROUND(SUM(montant_ttc), 3)    AS ca_ttc
FROM v_factures_detail
GROUP BY mois_emission;

-- 5. Synthèse par client
CREATE VIEW v_ca_par_client AS
SELECT
    client_id, client, secteur, segment, ville,
    COUNT(*)                         AS nb_factures,
    ROUND(SUM(montant_ttc), 3)       AS ca_ttc,
    ROUND(SUM(total_encaisse), 3)    AS total_encaisse,
    ROUND(SUM(reste_a_payer), 3)     AS reste_a_payer,
    ROUND(100 * SUM(total_encaisse) / NULLIF(SUM(montant_ttc), 0), 1) AS taux_recouvrement_pct
FROM v_factures_detail
GROUP BY client_id, client, secteur, segment, ville;

-- 6. Recouvrement par secteur
CREATE VIEW v_recouvrement_par_secteur AS
SELECT
    COALESCE(secteur, 'Non renseigné') AS secteur,
    COUNT(*)                         AS nb_factures,
    ROUND(SUM(montant_ttc), 3)       AS ca_ttc,
    ROUND(SUM(total_encaisse), 3)    AS total_encaisse,
    ROUND(SUM(reste_a_payer), 3)     AS reste_a_payer,
    ROUND(100 * SUM(total_encaisse) / NULLIF(SUM(montant_ttc), 0), 1) AS taux_recouvrement_pct
FROM v_factures_detail
GROUP BY COALESCE(secteur, 'Non renseigné');

-- Documentation (lue par le LLM)
COMMENT ON VIEW v_encaissements_detail IS 'Un encaissement par ligne, avec banque, client, secteur, segment, ville et mois. A utiliser pour toute question sur les sommes encaissées.';
COMMENT ON VIEW v_factures_detail IS 'Une facture par ligne, avec client, montant encaissé, reste à payer et retard (en_retard, jours_retard). A utiliser pour les impayés et retards.';
COMMENT ON VIEW v_encaissements_mensuels_banque IS 'Agrégat MENSUEL : une ligne par mois et par banque (total encaissé, nombre d''encaissements). Pour une période entière, faire SUM(...) GROUP BY nom_banque ; pour une moyenne, SUM(montant_total)/SUM(nb_encaissements).';
COMMENT ON VIEW v_ca_mensuel IS 'Agrégat MENSUEL : une ligne par mois d''émission (CA HT, CA TTC, nombre de factures). Pour plusieurs mois, utiliser SUM(...).';
COMMENT ON VIEW v_ca_par_client IS 'Par client : CA TTC, total encaissé, reste à payer et taux de recouvrement en pourcentage.';
COMMENT ON VIEW v_recouvrement_par_secteur IS 'Par secteur d''activité : CA TTC, encaissé, reste à payer et taux de recouvrement en pourcentage.';
COMMENT ON COLUMN v_encaissements_detail.mois IS 'Premier jour du mois de l''encaissement (ex: 2026-10-01).';
COMMENT ON COLUMN v_factures_detail.reste_a_payer IS 'Montant TTC moins encaissements reçus, en TND.';
COMMENT ON COLUMN v_factures_detail.jours_retard IS 'Jours de retard par rapport à l''échéance ; NULL si payée ou pas encore échue.';
