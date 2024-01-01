PLAYERS=liquipedia_scripts/data/ept-cups-known-players.csv
ept:
ifndef R
	$(error Please set R)
endif
ifndef N
	$(error Please set N)
endif
	tox -edev -- lp-ept-cups participants $R $N; ./tools/results-loop $R $N

add-players:
	# All the new players to add must be in a file named "cynical":
	# $ cat cynical
	# add Pie not pl z https://play.eslgaming.com/player/19418473
	# add Snoxtar notable https://play.eslgaming.com/player/9960122
	tools/cynical < cynical >> ${PLAYERS}
	# Sort that file so that humans can easily read it
	sort -k 6r,6 -k2,2 -t, -o ${PLAYERS} ${PLAYERS}
	# Generate a nice commit, but let a human push the work
	git add ${PLAYERS}
	git commit -m "$$(git diff --staged | awk -F, '/^+[^+]/ {print $$2}' | tr '\n' ',' | sed 's/,/, /g' | sed 's/, $$//')"

check:
	# This will print the IDs of duplicated players if there are any.
	# Silent otherwise.
	cut -d , -f 1 ${PLAYERS} | sort | uniq -d
