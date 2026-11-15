# Publishing BottleNeck on GitHub

The release archive is ready for a public repository, but it has not been pushed or pinned by this package builder. The steps below assume the intended repository slug is `Jelofen1962/BottleNeck`. If you choose another name, update the GitHub URLs in `README.md`, `.github/ISSUE_TEMPLATE/config.yml` and `SECURITY.md` first.

## Create the repository

On GitHub, create a new **public** repository named `BottleNeck` under `Jelofen1962`. Don't ask GitHub to create another README, `.gitignore` or license; this source archive already contains those files.

Before pushing, inspect the tree and make sure it contains no local `data/`, `backups/`, `logs/`, `.env`, SQLite databases or uploaded files.

## Push the stable source

From the extracted project root:

```bash
git init
git add .
git status
git commit -m "release: BottleNeck v1.1.0"
git branch -M main
git remote add origin https://github.com/Jelofen1962/BottleNeck.git
git push -u origin main
```

Review `git status` before the commit. Runtime data must never enter the repository.

## Publish the release archive

After the main branch is on GitHub:

```bash
python scripts/ui_audit.py
python scripts/build_release.py
python scripts/verify_release.py dist/BottleNeck-v1.1.0-production.zip

git tag -a v1.1.0 -m "BottleNeck v1.1.0"
git push origin v1.1.0
```

The tag workflow runs the checks and attaches the source ZIP and SHA-256 sidecar to the GitHub release. You can also upload the two files from `dist/` manually through the Releases page.

## Repository settings

- Add a short description: `Self-hosted Persian-first team workspace for tasks, notes, chat and shared files.`
- Add topics such as `self-hosted`, `team-workspace`, `fastapi`, `sqlite`, `project-management`, `persian` and `rtl`.
- Enable Issues. Enable Discussions if you want a separate place for questions and design proposals.
- Enable private vulnerability reporting after checking the contact method in `SECURITY.md`.
- Protect `main` and require the `CI / Python and frontend checks` workflow before merging.
- Keep the MIT license visible in the repository settings.

## Pin it to the profile

Once the public repository exists, open the GitHub profile for [Jelofen1962](https://github.com/Jelofen1962), choose **Customize your pins**, and select `BottleNeck`. GitHub controls profile pins; this project package can't change that setting.

## Replace the README hero with a real screenshot

The existing `docs/assets/readme-hero.svg` is an illustration. Capture the actual v1.1.0 UI using synthetic data, save a wide screenshot as `docs/assets/readme-hero.webp`, and change the image path at the top of `README.md`. Remove personal names, email addresses, private chat and real workspace files before committing it.
