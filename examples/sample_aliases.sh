# Example rc-file snippet for `aliasmine --existing`.
# aliasmine understands bash/zsh `alias`, fish `alias`, and fish `abbr` lines,
# and silently skips everything else — so pointing it at a whole .zshrc works.

export EDITOR=vim  # ignored: not an alias

alias gs='git status'
alias gl="git log --oneline"
alias ga='git add -p' gc='git commit'   # two on one line, bash-style

# fish dialects are fine too:
alias gd 'git diff'
abbr -a dcu 'docker compose up -d'
