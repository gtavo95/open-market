#!/usr/bin/env bash
#
# ingest.sh — from a datasheet PDF to an OKF page, in three stages with different owners.
#
#   1. raw/*.pdf      -> raw/md/*.md      docling. Deterministic, no judgment. Disposable: it can be
#                                         rerun in full without losing anything.
#   2. raw/md/*.md    -> products/*.md    the page skeleton: frontmatter, "# Datasheet" with the raw
#                                         text and the empty sections still to curate.
#                                         Writes ONLY files that do not exist.
#   3. products/*.md                      edited by a person. It is the source of truth and this
#                                         script NEVER overwrites it.
#
# That last line is the invariant: if stage 2 ever stepped on a curated page, human work would be
# lost without warning. That is why, when a PDF changes and the page already exists, the script
# converts the new text to raw/md/ so it can be compared, warns, and leaves the page alone.
#
# State lives in sources.tsv (sha256 <tab> pdf <tab> page), which IS committed even though raw/ is
# ignored. It is what makes "we have not updated in eight months" not a problem: the manifest says
# what changed since the last run, not anybody's memory.
#
# Usage:
#   ./ingest.sh                  converts what is new and changed, creates the missing pages
#   ./ingest.sh --status         only reports; converts and writes nothing
#   ./ingest.sh --accept         seals the current hashes ("I already reviewed the drift")
#   ./ingest.sh --force          reconverts everything to raw/md/ (still does not touch products/)
#   ./ingest.sh Sproutvane.pdf …     limits the run to those PDFs
#
set -euo pipefail

cd "$(dirname "$0")"

RAW=raw
MD=raw/md
PAGES=products
MANIFEST=sources.tsv
ORG="${OKF_ORG:-demo}"

MODE=run
FORCE=0
declare -a ONLY=()

while [ $# -gt 0 ]; do
	case "$1" in
	--status) MODE=status ;;
	--accept) MODE=accept ;;
	--force) FORCE=1 ;;
	-h | --help)
		sed -n '2,30p' "$0" | sed 's/^# \{0,1\}//'
		exit 0
		;;
	-*)
		echo "ingest.sh: unknown option: $1" >&2
		exit 2
		;;
	*) ONLY+=("$(basename "$1")") ;;
	esac
	shift
done

command -v docling >/dev/null || {
	echo "ingest.sh: docling is missing (uv tool install docling)" >&2
	exit 1
}

if command -v shasum >/dev/null; then
	sha() { shasum -a 256 "$1" | cut -d' ' -f1; }
else
	sha() { sha256sum "$1" | cut -d' ' -f1; }
fi

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
: >"$TMP/next.tsv"
: >"$TMP/log.txt"
: >"$TMP/seen.txt"
: >"$TMP/slugs.txt"

# fold folds Spanish accents to their plain form, the same as okf.NormName in the wiki module.
# It goes before lowercasing because tr only maps the ASCII range without breaking UTF-8.
fold() {
	sed 's/[ÁÀÂÄáàâä]/a/g; s/[ÉÈÊËéèêë]/e/g; s/[ÍÌÎÏíìîï]/i/g; s/[ÓÒÔÖóòôö]/o/g; s/[ÚÙÛÜúùûü]/u/g; s/[Ññ]/n/g'
}

# slug is the file name: lowercase, no accents, one hyphen per run of separators.
slug() { printf '%s' "$1" | fold | tr 'A-Z' 'a-z' | sed 's/[^a-z0-9]\{1,\}/-/g; s/^-//; s/-$//'; }

# normname is the page's join key, the same one okf.NormName computes: lowercase, accents folded and
# spaces collapsed. If here and there normalized differently, the join would fail silently.
normname() { printf '%s' "$1" | fold | tr 'A-Z' 'a-z' | tr -s ' \t' ' ' | sed 's/^ //; s/ $//'; }

# lookup returns the hash the page that corresponds to that PDF today was generated with. Without a
# manifest —the first run— it returns empty, which is exactly "this PDF is new".
lookup() {
	[ -f "$MANIFEST" ] || return 0
	awk -F'\t' -v n="$1" '$2 == n { print $1 }' "$MANIFEST" | head -1
}

# page_of returns the path the manifest already recorded for that PDF. Deriving it from the file name
# breaks as soon as someone renames the page to the commercial name: the script does not find it,
# takes it as missing and writes a skeleton over the curation, which is exactly what the invariant
# forbids. A PDF without a row is a new one, it returns empty, and the caller falls back to the slug.
page_of() {
	[ -f "$MANIFEST" ] || return 0
	awk -F'\t' -v n="$1" '$2 == n { print $3 }' "$MANIFEST" | head -1
}

# convert runs docling on a PDF and leaves the markdown in raw/md/<slug>.md. The previous version is
# not deleted: it is kept as .prev.md, which is the only thing a change can be diffed against, because
# raw/ is outside git and there is no history to consult.
convert() {
	local pdf="$1" slug="$2" out="$MD/$2.md"
	mkdir -p "$MD"
	[ -f "$out" ] && mv "$out" "$MD/$slug.prev.md"
	rm -rf "$TMP/dl"
	docling convert "$pdf" \
		--from pdf --to md \
		--image-export-mode placeholder \
		--device mps \
		--no-abort-on-error \
		--output "$TMP/dl" >"$TMP/docling.log" 2>&1 || {
		echo "  ✗ docling failed; see $TMP/docling.log" >&2
		[ -f "$MD/$slug.prev.md" ] && mv "$MD/$slug.prev.md" "$out"
		return 1
	}
	local produced
	produced="$(find "$TMP/dl" -name '*.md' | head -1)"
	[ -n "$produced" ] || {
		echo "  ✗ docling produced no markdown for $pdf" >&2
		return 1
	}
	mv "$produced" "$out"
}

# write_page builds the OKF page skeleton. The body follows the vocabulary okf.ParseDoc reads:
# sections are level-one "# " with an exact name, and everything inside "# Datasheet" is free text.
# That is why docling's markdown goes there and its headings are lowered one level: what comes out
# of a PDF is the datasheet, not the structure of the page.
write_page() {
	local pdf_name="$1" slug="$2" title="$3" page="$4"
	local norm
	norm="$(normname "$title")"
	{
		printf -- '---\n'
		printf 'type: product\n'
		printf 'title: "%s"\n' "$title"
		printf 'tags:\n'
		printf 'org_id: %s\n' "$ORG"
		printf 'normalized_name: %s\n' "$norm"
		printf 'wiki_id: "%s"\n' "$norm"
		printf 'bucket_path: ""\n'
		printf 'state: current\n'
		printf 'reference_id: "%s"\n' "$pdf_name"
		# 'generated' says who produced the content, and here it is this script. It is the repo's
		# invariant written where a machine reads it: while it says 'process:ingest.sh', the page is the
		# raw skeleton and nobody has curated it yet. Whoever curates it changes it to 'human:<id>' with
		# that day's date, and from then on the file belongs to a person. Until today that lived in an
		# HTML comment.
		printf 'generated: { by: process:ingest.sh, at: %s }\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
		# Provenance goes in the frontmatter, which is where the OKF SPEC asks for it (§5.1). The
		# datasheet is the only source this script knows; the pricelist and the equivalents are added by
		# whoever curates, because they do not come from the datasheet PDF.
		printf 'sources:\n'
		printf '  - id: datasheet\n'
		printf '    resource: "/raw/%s"\n' "$pdf_name"
		printf '    title: "Manufacturer'"'"'s datasheet"\n'
		printf -- '---\n'
		cat <<-EOF

			<!--
			Skeleton generated by ingest.sh from raw/$pdf_name. ingest.sh does not write this file
			again: from here on it is human curation. Still to do:
			  - generated: change it to human:<id> with the day's date when curation is done
			  - tags: the tenant's types (ontology/product-types.md), empty today
			  - normalized_name / wiki_id: check against the real commercial name
			  - # Presentations: sizes and prices, which do not come from the datasheet. When they go
			    in, their entry goes in sources too, with the price list and its page
			  - # Ingredients and # Agronomy: fill in by hand
			  - # Datasheet: review the OCR; docling confuses uncommon proper nouns
			-->

			# Summary
			$title

			# Presentations
			| Size | Unit | Price | Price/unit | Currency |
			|---|---|---|---|---|

			# Ingredients

			# Datasheet
		EOF
		# The PDF's "# " go down one level and the image placeholders go away. okf.parseSections already
		# treats a reserved heading inside the datasheet as content, so lowering them is just in case.
		# "# Datasheet" is the last section and nothing closes it: the PDF's text runs to the end.
		sed 's/^# /## /; /^<!-- image -->$/d' "$MD/$slug.md" | awk 'NF { p = 1 } p'
	} >"$page"
}

wanted() {
	[ ${#ONLY[@]} -eq 0 ] && return 0
	local n
	for n in "${ONLY[@]}"; do [ "$n" = "$1" ] && return 0; done
	return 1
}

added=0
changed=0
pending=0
unchanged=0

shopt -s nullglob
for pdf in "$RAW"/*.pdf; do
	name="$(basename "$pdf")"
	stem="${name%.pdf}"
	s="$(slug "$stem")"
	title="$(printf '%s' "$stem" | tr '_' ' ' | tr -s ' ')"
	page="$(page_of "$name")"
	page="${page:-$PAGES/$s.md}"
	hash="$(sha "$pdf")"
	old="$(lookup "$name")"
	printf '%s\n' "$name" >>"$TMP/seen.txt"

	# Two PDFs with different names can give the same slug ("Leafvane Ca+B" and "Leafvane_Ca_B"). Without
	# this cut the second would be skipped silently, because stage 2 does not step on existing pages.
	if grep -qxF "$s" "$TMP/slugs.txt"; then
		echo "  ✗ $name collides on slug with another PDF ($s); rename one of the two" >&2
		continue
	fi
	printf '%s\n' "$s" >>"$TMP/slugs.txt"

	if ! wanted "$name"; then
		printf '%s\t%s\t%s\n' "${old:-$hash}" "$name" "$page" >>"$TMP/next.tsv"
		continue
	fi

	if [ "$MODE" = accept ]; then
		printf '%s\t%s\t%s\n' "$hash" "$name" "$page" >>"$TMP/next.tsv"
		continue
	fi

	if [ -z "$old" ]; then
		state=new
	elif [ "$old" = "$hash" ]; then
		state=same
	else
		state=changed
	fi
	if [ "$state" = same ] && [ ! -f "$page" ]; then state=no-page; fi
	if [ "$FORCE" = 1 ] && [ "$state" = same ]; then state=reconvert; fi

	case "$state" in
	same)
		unchanged=$((unchanged + 1))
		printf '%s\t%s\t%s\n' "$hash" "$name" "$page" >>"$TMP/next.tsv"
		;;

	new | no-page | reconvert)
		if [ "$MODE" = status ]; then
			echo "  new        $name -> $page"
			added=$((added + 1))
			printf '%s\t%s\t%s\n' "${old:-$hash}" "$name" "$page" >>"$TMP/next.tsv"
			continue
		fi
		echo "  converting $name"
		convert "$pdf" "$s" || {
			printf '%s\t%s\t%s\n' "${old:-$hash}" "$name" "$page" >>"$TMP/next.tsv"
			continue
		}
		if [ -f "$page" ]; then
			echo "  = $page already exists, left alone"
		else
			write_page "$name" "$s" "$title" "$page"
			echo "  + $page"
			printf -- '- **Creation** `%s` from `%s`. Uncurated skeleton.\n' "$page" "$name" >>"$TMP/log.txt"
			added=$((added + 1))
		fi
		printf '%s\t%s\t%s\n' "$hash" "$name" "$page" >>"$TMP/next.tsv"
		;;

	changed)
		changed=$((changed + 1))
		if [ "$MODE" = status ]; then
			echo "  changed    $name -> $page"
			printf '%s\t%s\t%s\n' "$old" "$name" "$page" >>"$TMP/next.tsv"
			continue
		fi
		echo "  converting $name (changed)"
		convert "$pdf" "$s" || {
			printf '%s\t%s\t%s\n' "$old" "$name" "$page" >>"$TMP/next.tsv"
			continue
		}
		if [ -f "$page" ]; then
			# The hash is NOT sealed: the warning has to come out again on every run until someone
			# looks at the diff and confirms with --accept. A warning that turns itself off is not a warning.
			echo "  ! $page is out of date; diff raw/md/$s.prev.md raw/md/$s.md"
			pending=$((pending + 1))
			printf '%s\t%s\t%s\n' "$old" "$name" "$page" >>"$TMP/next.tsv"
		else
			write_page "$name" "$s" "$title" "$page"
			echo "  + $page"
			printf -- '- **Creation** `%s` from `%s`. Uncurated skeleton.\n' "$page" "$name" >>"$TMP/log.txt"
			printf '%s\t%s\t%s\n' "$hash" "$name" "$page" >>"$TMP/next.tsv"
		fi
		;;
	esac
done

# A PDF no longer in raw/ does not delete its row: if it comes back identical, it need not be
# reconverted. And its page is not deleted either — the model has LOGICAL deletion (state), which is
# right here: a discontinued product keeps being named in conversations and the wiki has to be able
# to say what happened to it.
if [ -f "$MANIFEST" ] && [ ${#ONLY[@]} -eq 0 ]; then
	while IFS=$'\t' read -r h n p; do
		[ -n "${n:-}" ] || continue
		grep -qxF "$n" "$TMP/seen.txt" && continue
		printf '%s\t%s\t%s\n' "$h" "$n" "$p" >>"$TMP/next.tsv"
		if [ -f "$p" ] && ! grep -q '^state: \(discontinued\|withdrawn\|out_of_stock\)' "$p"; then
			echo "  ? $p is still current but its PDF is no longer in raw/; state: discontinued?"
		fi
	done <"$MANIFEST"
fi

if [ "$MODE" != status ]; then
	sort -t$'\t' -k2,2 "$TMP/next.tsv" >"$MANIFEST"
fi

# index.md is generated by this script on every run. Do not edit it by hand: the SPEC treats it as a
# mechanical listing of the directory and okf.productRel skips it, so it is not a product page.
if [ "$MODE" != status ] && [ -d "$PAGES" ]; then
	{
		printf '# Products (index)\n\n'
		printf 'Generated by ingest.sh. This file is not a product page.\n\n'
		for p in "$PAGES"/*.md; do
			[ "$(basename "$p")" = index.md ] && continue
			t="$(sed -n 's/^title: "\(.*\)"$/\1/p' "$p" | head -1)"
			printf -- '- [%s](%s)\n' "${t:-$(basename "$p" .md)}" "$(basename "$p")"
		done
	} >"$PAGES/index.md"
fi

# The bundle's log: ISO date, newest first, the action in bold at the start of the entry.
if [ -s "$TMP/log.txt" ] && [ "$MODE" != status ]; then
	today="$(date +%Y-%m-%d)"
	[ -s log.md ] || printf '# Log\n' >log.md
	awk -v today="$today" -v ef="$TMP/log.txt" '
		function entries(   line) { while ((getline line < ef) > 0) print line; close(ef) }
		!done && /^## / {
			if ($0 == "## " today) { print; print ""; entries(); done = 1; next }
			print "## " today; print ""; entries(); print ""
			done = 1; print; next
		}
		{ print }
		END { if (!done) { print ""; print "## " today; print ""; entries() } }
	' log.md >"$TMP/log.md" && mv "$TMP/log.md" log.md
fi

echo
echo "unchanged: $unchanged · new: $added · PDFs changed: $changed · pages to review: $pending"
if [ "$pending" -gt 0 ]; then
	echo "review the diffs and when they are up to date: ./ingest.sh --accept"
fi
