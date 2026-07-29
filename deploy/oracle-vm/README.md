# Déploiement cloud — Oracle Cloud Always Free

Remplace la tâche planifiée Windows par une petite VM Linux toujours allumée,
gratuite en permanence (pas un essai de 12 mois). Le code, la base SQLite et
la logique métier ne changent pas — seul l'hébergement change.

## Ce que tu dois faire toi-même (compte + VM)

Ces étapes touchent à un compte personnel et à une carte bancaire (pour la
vérification d'identité Oracle, aucun prélèvement sur l'offre Always Free) —
je ne les fais pas à ta place.

1. Créer un compte sur [cloud.oracle.com](https://cloud.oracle.com) (offre
   "Always Free").
2. Créer une instance de calcul :
   - **Image** : Ubuntu 22.04 (ou 24.04) — Always Free éligible.
   - **Shape** : `VM.Standard.A1.Flex` (ARM Ampere, jusqu'à 4 OCPU/24 Go RAM,
     Always Free) si disponible dans ta région. **Si tu tombes sur "Out of
     host capacity"** (fréquent sur l'offre ARM gratuite selon la région/le
     moment), rabats-toi sur `VM.Standard.E2.1.Micro` (AMD, toujours Always
     Free, 1 Go RAM — un peu juste avec Chromium/Playwright, voir note
     mémoire ci-dessous) ou réessaie plus tard sur une autre région.
   - **Clé SSH** : laisse Oracle en générer une paire, télécharge la clé
     privée (tu en auras besoin pour te connecter).
   - **Réseau** : la security list par défaut n'autorise que le SSH entrant
     (port 22) — c'est suffisant, ce projet n'a besoin d'aucun port ouvert
     (uniquement du trafic sortant : scraping, Gemini, Gmail). Ne rien ouvrir
     de plus.
3. Noter l'IP publique de l'instance et te connecter une première fois pour
   valider que le SSH fonctionne :
   ```bash
   ssh -i /chemin/vers/ta_cle.key ubuntu@<IP-de-la-VM>
   ```

**Si tu as pris le shape AMD 1 Go RAM** : Playwright/Chromium peut swapper
sous charge. Si `provision_vm.sh` échoue ou que les runs plantent sans raison
claire, ajoute un fichier de swap de 2 Go avant de relancer :
```bash
sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile
```

## ⚠️ Point bloquant à ne pas oublier : le consentement OAuth reste local

`InstalledAppFlow.run_local_server()` (dans `src/notifications/gmail_auth.py`)
ouvre un navigateur — impossible à faire tourner sur une VM sans écran. Le
consentement OAuth se fait **toujours** sur une machine avec navigateur
(comme aujourd'hui), jamais sur la VM. La VM n'a besoin que du `token.json`
qui en résulte : une fois dessus, `creds.refresh()` renouvelle silencieusement
l'accès sans navigateur, indéfiniment (maintenant que l'app est en
"production" — voir CLAUDE.md, plus d'expiration à 7 jours).

Concrètement, après le passage en production (déjà fait) :
1. Supprime `token.json` en local et relance `main.py` une fois en local pour
   forcer un nouveau consentement OAuth avec Clara devant l'écran (elle verra
   l'écran "Application non validée" → "Paramètres avancés" → continuer).
2. Transfère ce nouveau `token.json` vers la VM avec `sync_secrets.sh`
   (ci-dessous). C'est la dernière fois que Clara doit intervenir pour ça.

## Étapes de déploiement (une fois la VM prête)

Depuis ta machine (Git Bash), à la racine du projet :

```bash
# 1. Code (sans secrets ni données)
./deploy/sync_code.sh ubuntu@<IP-de-la-VM>

# 2. Provisioning système (Python, venv, Playwright, fuseau horaire Europe/Paris)
ssh ubuntu@<IP-de-la-VM> "cd /opt/clara-am && ./deploy/provision_vm.sh"

# 3. Secrets et données (.env, client_secret.json, token.json, cv.txt,
#    reference_letter.txt, offres.db existant pour ne pas re-classer)
./deploy/sync_secrets.sh ubuntu@<IP-de-la-VM>

# 4. Installer et activer les timers systemd
ssh ubuntu@<IP-de-la-VM> "cd /opt/clara-am && ./deploy/install_systemd.sh"
```

## Vérifier que ça tourne

```bash
ssh ubuntu@<IP-de-la-VM>

systemctl list-timers 'clara-am*'          # prochaines exécutions prévues
sudo systemctl start clara-am.service      # forcer un run tout de suite
journalctl -u clara-am.service -f          # suivre en direct
tail -f /opt/clara-am/logs/run_$(date +%Y%m%d).log   # log détaillé du jour
```

## Mettre à jour le code plus tard

Relance simplement `sync_code.sh` — sans risque, ne touche jamais à
`data/`, `.venv/` ni `logs/` côté VM. Si `requirements.txt` a changé :

```bash
ssh ubuntu@<IP-de-la-VM> "/opt/clara-am/.venv/bin/pip install -r /opt/clara-am/requirements.txt"
```

Aucun redémarrage de service nécessaire (les timers relancent `main.py` à
chaque déclenchement, donc le nouveau code est pris en compte au run suivant).

## Ce que ça remplace, concrètement

| Ancien (Windows Task Scheduler) | Nouveau (VM Oracle Cloud) |
|---|---|
| `task_scheduler.xml` (2 triggers) | `clara-am-baseline.timer` + `clara-am-daytime.timer` |
| `run.ps1` | `deploy/run.sh` |
| Exécution seulement si le PC est allumé et une session ouverte | VM toujours allumée, 24/7 |
| `logs/run_AAAAMMJJ.log` | Identique, sur la VM (+ `journalctl` en secours) |
| `scripts/validate_offers.py` lancé à la main | `clara-am-validate.timer`, quotidien à 04h15 |
