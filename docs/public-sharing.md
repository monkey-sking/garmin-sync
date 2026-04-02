# Public Sharing Notes

This repository's current working tree has been cleaned for public sharing:
- local planning logs were removed
- machine-specific absolute paths were removed from public docs
- runtime artifacts stay ignored

## Important
Deleting files from the current tree does **not** remove them from existing git history.

If this repository's earlier commits contained local paths, operator notes, or other private development context, the safest public publish flow is to publish from a fresh history.

## Recommended Publish Options
### Option 1: Fresh public repository
Create a new repository from the current cleaned snapshot and publish that repository.

This is the safest option when earlier local commits contained private context.

### Option 2: Orphan public branch
If you want to keep using this repository, create an orphan branch from the cleaned working tree and publish that branch instead of the old branch history.

Typical flow:

```bash
git switch --orphan public-main
git add .
git commit -m "Initial public release"
```

Then push `public-main` to a new GitHub repository.

## Before You Push
- Recheck `git status`
- Recheck `git diff --cached`
- Recheck `.gitignore`
- Make sure no runtime data, local exports, or personal notes are staged
