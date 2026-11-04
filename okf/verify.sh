#!/usr/bin/env bash
#
# verify.sh — says two different things about each page, and the difference matters:
#
#   ERROR    the page cannot be read. The reader discards it as a PageError and it disappears from
#            the catalog silently: the file exists, the product does not. Fix it now.
#   pending  the page reads fine but still needs curation. It is data that is not there yet, not a defect.
#
# With no arguments it checks the whole bundle. With arguments, only those pages.
#
# Pages under products/ get the full check. The rest of the bundle is only held to the OKF SPEC's
# conformance floor: parseable frontmatter and a non-empty 'type' on every .md that is not a
# reserved name. That floor was missing, and that is why company_info/ spent months without 'type'
# with nothing saying so: the bundle did not conform and the dashboard said everything was fine.
#
# Exits 1 if there is any ERROR, so it can serve as a gate before a commit.
#
set -uo pipefail
cd "$(dirname "$0")"

PAGES=products

# The OKF reader's section vocabulary. A "# " that is not listed here does not open a section: it
# stays as loose prose of the previous document, so its content is lost without warning.
SECTIONS="Summary Types Presentations Ingredients Equivalents Agronomy Datasheet"

errors=0
others=0
reviewed=0
machine=0
uncurated=0
no_tags=0
no_prices=0
no_agro=0
no_certified=0
pages=0
axes=0
concepts=0
vocab_broken=0
VOCAB=""
PARENTS=""

# The agronomic profile is JSON and checking it takes a JSON parser. If jq is missing, every page
# with a profile gets an ERROR instead of being skipped: a check that turns itself off leaves the
# dashboard green exactly when it stopped looking.
NO_JQ=0
command -v jq >/dev/null 2>&1 || NO_JQ=1

err() {
	printf 'ERROR  %s: %s\n' "$1" "$2"
	errors=$((errors + 1))
}

# The actor convention of §7: 'human:<id>' a person, 'process:<id>' an automated process,
# 'producer/version' an agent. It matters that it is spelled right for a reason you cannot see:
# consumers classify trust by looking at the 'human:' prefix, so a mistyped actor does not fail
# anywhere, it simply stops counting as human review and the page stays unverified forever. It is
# the easiest mistake for a hand editing the frontmatter to make.
actor_ok() {
	printf '%s\n' "$1" | grep -qE '^(human:[A-Za-z0-9._-]+|process:[A-Za-z0-9._-]+|[A-Za-z0-9._-]+/[A-Za-z0-9._-]+)$'
}

# actors pulls the 'by' values out of a block, one per line. It works the same for the compact form
# '{ by: x, at: y }' as for the §5.2 list of several verifiers.
actors() {
	printf '%s\n' "$1" | grep -o 'by:[[:space:]]*[^,}[:space:]]*' | sed 's/^by:[[:space:]]*//'
}

# --- the tenant's vocabulary ---
#
# ontology/ closes the hole that per-page review cannot close by itself: one page writing
# "R. Dominicana", another "Rep. Dominicana", and the two staying two countries forever.
# One file per axis, and the file name is the axis id.
#
# An axis that does NOT exist demands nothing. While ontology/<axis>.md is absent, that field is free
# text and no page fails because of it; the day it exists, an extra term is a curation error. That
# is why adding the leaf is what makes the axis mandatory, and there is no list of required axes
# somewhere else that can be forgotten.
#
# An incoherent leaf is NOT a problem of that leaf alone. An alias that resolves to two concepts
# keeps the reader from building the ontology, and without an ontology nothing is validated:
# everything passes. Validation turns itself off and no page looks broken. That is why a broken leaf
# here cuts the page review short and says so, instead of leaving the dashboard green.
ONTO=ontology

# The normalization a term is compared with: accents folded, lowercase, spaces collapsed. It has to
# be THE SAME on both sides. If the leaf normalizes differently from the page, the join does not
# fail, it returns empty, and the term exists and does not resolve.
NORM_AWK='
function fold(s,   t) {
	t = s
	gsub(/Á/, "a", t); gsub(/á/, "a", t)
	gsub(/É/, "e", t); gsub(/é/, "e", t)
	gsub(/Í/, "i", t); gsub(/í/, "i", t)
	gsub(/Ó/, "o", t); gsub(/ó/, "o", t)
	gsub(/Ú/, "u", t); gsub(/ú/, "u", t)
	gsub(/Ñ/, "n", t); gsub(/ñ/, "n", t)
	gsub(/Ü/, "u", t); gsub(/ü/, "u", t)
	return t
}
function norm(s,   t) {
	t = tolower(fold(s))
	gsub(/^[ \t]+|[ \t]+$/, "", t)
	gsub(/[ \t]+/, " ", t)
	return t
}
'

# Reads the leaves and produces two things: ERR rows for whatever breaks the vocabulary, and the
# table T that a term is later resolved with. What gets rejected is what breaks the join SILENTLY: a
# repeated id, a nonexistent parent, a parent cycle, and above all an alias that points to two
# concepts, which gives no error anywhere and makes "chile" sometimes one thing and sometimes
# another depending on the position the file was read in.
VOCAB_AWK=$NORM_AWK'
BEGIN { FS = "|" }
function cell(n,   v) { v = $n; gsub(/^[ \t]+|[ \t]+$/, "", v); return v }
FNR == 1 {
	file = FILENAME
	axis = file; sub(/.*\//, "", axis); sub(/\.md$/, "", axis)
	in_table = 0
	warned = 0
	skip = (axis == "index")
	if (!skip) leaves[file] = axis
}
skip { next }
/^\|/ {
	# The concept table opens with its "| id |" header and not before. A leaf carries ONE table: the
	# reader starts consuming rows at the first one it finds, so an explanatory table above the
	# prose is read as concepts with backticked ids. It does not fail, it adds garbage to the
	# vocabulary.
	if (norm(cell(2)) == "id") { in_table = 1; next }
	if (cell(2) ~ /^-+$/) next
	if (!in_table) {
		if (!warned) {
			printf "ERR\t%s\tthere is a table before the concept table; the reader takes it as concepts\n", file
			warned = 1
		}
		next
	}
	id = cell(2)
	if (id == "") next
	k = axis SUBSEP norm(id)
	if (k in seen) { printf "ERR\t%s\tduplicate id \"%s\"\n", file, id; next }
	seen[k] = id
	parent[k] = cell(4); raw[k] = id; file_of[k] = file
	position[++n] = k
	counts[axis]++
	t = id
	if (cell(3) != "") t = t "," cell(3)
	if (cell(5) != "") t = t "," cell(5)
	m = split(t, parts, ",")
	for (i = 1; i <= m; i++) {
		nt = norm(parts[i])
		if (nt == "") continue
		tk = axis SUBSEP nt
		if (tk in owner && owner[tk] != id) {
			printf "ERR\t%s\tthe term \"%s\" resolves to \"%s\" and to \"%s\"\n", file, parts[i], owner[tk], id
			continue
		}
		owner[tk] = id
		printf "T\t%s\t%s\t%s\n", axis, nt, id
	}
}
END {
	# The parent-child relation, separately from the terms. Without it a check that asks "does this
	# concept reach that one?" has to compare flat ids, and answers no exactly when the datasheet
	# grouped by the parent, which is the normal case.
	for (i = 1; i <= n; i++) {
		k = position[i]
		split(k, p, SUBSEP); axis = p[1]
		pid = ""
		if (parent[k] != "") {
			pk = axis SUBSEP norm(parent[k])
			if (pk in seen) pid = seen[pk]
		}
		printf "P\t%s\t%s\t%s\n", axis, raw[k], pid
	}
	for (i = 1; i <= n; i++) {
		k = position[i]
		split(k, p, SUBSEP); axis = p[1]
		if (parent[k] == "") continue
		pk = axis SUBSEP norm(parent[k])
		if (!(pk in seen)) {
			printf "ERR\t%s\t\"%s\" hangs from a nonexistent parent \"%s\"\n", file_of[k], raw[k], parent[k]
			continue
		}
		cur = pk; depth = 0
		while (depth++ < 100) {
			if (cur == k) { printf "ERR\t%s\tparent cycle at \"%s\"\n", file_of[k], raw[k]; break }
			if (parent[cur] == "") break
			cur = axis SUBSEP norm(parent[cur])
		}
	}
	# An axis without concepts is not an empty axis, it is a leaf that could not be read: a misspelled
	# header, the table in another format. It gets reported, because the vocabulary loads anyway and
	# the axis stays declared with nothing inside, which accepts any term.
	for (a in leaves) if (!(leaves[a] in counts)) printf "ERR\t%s\tthe axis declares no concepts\n", a
	for (e in counts) printf "N\t%s\t%d\n", e, counts[e]
}'

# vocabulary builds the resolution table once. Without ontology/ there is nothing to build and the
# bundle is checked exactly as it was before the vocabulary existed.
vocabulary() {
	local output file message
	[ -d "$ONTO" ] || return 0
	ls "$ONTO"/*.md >/dev/null 2>&1 || return 0
	output="$(awk "$VOCAB_AWK" "$ONTO"/*.md)"
	VOCAB="$(printf '%s\n' "$output" | grep '^T	' | cut -f2-)"
	PARENTS="$(printf '%s\n' "$output" | grep '^P	' | cut -f2-)"
	axes="$(printf '%s\n' "$output" | grep -c '^N	')"
	concepts="$(printf '%s\n' "$output" | awk -F'\t' '$1 == "N" { n += $3 } END { print n + 0 }')"
	while IFS="$(printf '\t')" read -r _ file message; do
		[ -n "$file" ] || continue
		err "$file" "$message"
		vocab_broken=1
	done < <(printf '%s\n' "$output" | grep '^ERR	')
}

# check_terms reads terms on stdin and reports the ones the axis does not know. A term that does not
# resolve takes the page out of the whole catalog, not just out of the axis: the reader discards it
# the same as a malformed one, because a page that cannot be retrieved by crop and is shown anyway
# lies about what can be found.
check_terms() {
	local p="$1" axis="$2" label="$3" t
	[ -f "$ONTO/$axis.md" ] || { cat >/dev/null; return 0; }
	[ "$vocab_broken" -eq 0 ] || { cat >/dev/null; return 0; }
	while IFS= read -r t; do
		[ -n "$t" ] || continue
		err "$p" "$label outside the vocabulary: '$t' (axis $axis)"
	done < <(awk -F'\t' -v e="$axis" "$NORM_AWK"'
		NR == FNR { if ($1 == e) known[$2] = 1; next }
		{
			t = norm($0)
			if (t == "" || t in known || t in said) next
			said[t] = 1
			print $0
		}
	' <(printf '%s\n' "$VOCAB") -)
}

# check_ids is check_terms, stricter: in the agronomic profile and in the tags the concept's ID goes,
# not an alias. An alias resolves anyway, so it fails nowhere and the page ends up written
# differently from the other 37. The next time someone compares two pages field by field,
# "hectare" and "ha" are two different values even though they mean the same thing.
check_ids() {
	local p="$1" axis="$2" label="$3" t
	[ -f "$ONTO/$axis.md" ] || { cat >/dev/null; return 0; }
	[ "$vocab_broken" -eq 0 ] || { cat >/dev/null; return 0; }
	while IFS="$(printf '\t')" read -r t id; do
		[ -n "$t" ] || continue
		case "$id" in
		"") err "$p" "$label outside the vocabulary: '$t' (axis $axis)" ;;
		*) err "$p" "$label '$t' is an alias; the id goes here: '$id'" ;;
		esac
	done < <(awk -F'\t' -v e="$axis" "$NORM_AWK"'
		NR == FNR { if ($1 == e) { known[$2] = $3 } ; next }
		{
			t = norm($0)
			if (t == "" || t in said) next
			said[t] = 1
			if (!(t in known)) { print $0 "\t"; next }
			if (known[t] != $0) print $0 "\t" known[t]
		}
	' <(printf '%s\n' "$VOCAB") -)
}

# fm_list pulls the values of a frontmatter list key, one per line. It accepts the indented list and
# the one that is not: both are legal YAML and the difference does not show when reading. When the
# reader accepts both and the check only one, the tags exist and the dashboard says they are missing.
fm_list() {
	awk -v k="$2" '
		$0 == "---" { if (++dashes == 2) exit; next }
		dashes != 1 { next }
		$0 == k ":" { f = 1; next }
		f && /^[[:space:]]*- / { sub(/^[[:space:]]*- /, ""); sub(/[[:space:]]+$/, ""); print; next }
		f && /^[[:space:]]*$/ { next }
		f { f = 0 }
	' "$1"
}

# resolve translates terms to ids of the axis, one per line. A term that does not resolve comes out
# with a leading "?", so whoever compares sets sees the difference instead of a blank.
resolve() {
	awk -F'\t' -v e="$1" "$NORM_AWK"'
		NR == FNR { if ($1 == e) id[$2] = $3; next }
		{ t = norm($0); if (t == "") next; print (t in id) ? id[t] : "?" $0 }
	' <(printf '%s\n' "$VOCAB") -
}

# --- the agronomic profile ---
#
# The profile is embedded JSON and the module validates it ON READ (internal/okf/agronomy.go). An
# incoherent profile does not leave the page half done: it discards it whole, dose and all. That is
# why what the module rejects is also rejected here, before the commit, where there is still someone
# to tell.
#
# And also what the module does NOT look at, which is half of what can go wrong:
#
#   - that each term resolves against ontology/, and that it is the id and not an alias. "hectare"
#     resolves to 'ha' and never fails, and leaves a page written differently from the other
#     thirty-seven without anything saying so.
#   - that each source_ref points to a source that exists. FORMAT.md has always said it is mandatory;
#     the module does not check it, so until today nobody checked it.
#   - that a listed_crops_only profile says the same about crops as the frontmatter. They are the
#     same fact written twice, and two copies nobody compares diverge. An all_crops profile does not
#     list crops, so there is nothing to compare there.
agronomy() {
	local p="$1" fm="$2" json fences REGIMENS
	grep -q '^# Agronomy$' "$p" || return 0
	if [ "$NO_JQ" = 1 ]; then
		err "$p" "jq is needed to check the agronomic profile and it is not installed"
		return 1
	fi
	# The reader consumes the FIRST json block of the section. A second block gives no error
	# anywhere: it stays as decoration, and whoever edits it believes they changed the profile.
	fences="$(awk '/^# Agronomy$/ { f = 1; next } /^# / { f = 0 } f && /^```json$/ { n++ } END { print n + 0 }' "$p")"
	if [ "$fences" != 1 ]; then
		err "$p" "'# Agronomy' has $fences json blocks; the reader only looks at the first"
		[ "$fences" = 0 ] && return 1
	fi
	json="$(awk '/^# Agronomy$/ { f = 1; next } f && /^```json$/ { g = 1; next } g && /^```$/ { exit } g' "$p")"
	if ! printf '%s' "$json" | jq -e . >/dev/null 2>&1; then
		err "$p" "the agronomic profile is not valid JSON"
		return 1
	fi
	jqv() { printf '%s' "$json" | jq -r "$1" 2>/dev/null; }

	[ "$(jqv '.schema // ""')" = "product/agronomy/v1" ] ||
		err "$p" "the profile declares another schema; the module rejects it without reading it"

	# Domains and scope: the same rules as the module, for the same reasons. A non-agricultural
	# profile that lists crops anyway states two things that cannot both be true.
	local domains scope ncrops
	domains="$(jqv '(.application_domains // []) | join(" ")')"
	scope="$(jqv '.crop_scope // ""')"
	ncrops="$(jqv '(.crops // []) | length')"
	case " $domains " in
	"  ") err "$p" "the profile declares no application domain" ;;
	esac
	for d in $domains; do
		case "$d" in
		agriculture | aquaculture) ;;
		*) err "$p" "unknown application domain: '$d'" ;;
		esac
	done
	case " $domains " in
	*" agriculture "*)
		case "$scope" in
		all_crops) [ "$ncrops" = 0 ] || err "$p" "crop_scope all_crops with $ncrops crops listed" ;;
		listed_crops_only) [ "$ncrops" = 0 ] && err "$p" "crop_scope listed_crops_only with no crops" ;;
		*) err "$p" "an agricultural profile needs all_crops or listed_crops_only, it says '$scope'" ;;
		esac
		;;
	*)
		{ [ "$scope" = not_applicable ] && [ "$ncrops" = 0 ]; } ||
			err "$p" "a non-agricultural profile needs crop_scope not_applicable and no crops"
		;;
	esac

	check_ids "$p" crops "profile crop" < <(jqv '.crops[]?')
	check_ids "$p" targets "target" < <(jqv '.targets[]?.id')
	check_ids "$p" target-types "target type" < <(jqv '.targets[]?.kind')
	# The regimens at the top and those of the overrides are checked together: an invented unit inside
	# an override is just as fatal as in the default regimen, and more likely to slip through there.
	REGIMENS='[.default_regimens[]?, .overrides[]?.regimens[]?] | .[]'
	check_ids "$p" routes "application route" \
		< <(jqv "$REGIMENS | .route // empty" ; jqv '.overrides[]?.match.routes[]? // empty')
	check_ids "$p" units "dose unit" \
		< <(jqv "$REGIMENS | (.dose.unit? // empty), (.water_volume.unit? // empty)")
	check_ids "$p" bases "dose basis" \
		< <(jqv "$REGIMENS | (.dose.basis? // empty), (.water_volume.basis? // empty)")

	# A citation that cannot be followed is worse than none: the dose looks audited and is not.
	local source_ids
	source_ids="$(jqv '.sources[]?.id')"
	while IFS= read -r sref; do
		[ -n "$sref" ] || continue
		printf '%s\n' "$source_ids" | grep -qxF -- "$sref" ||
			err "$p" "source_ref '$sref' points to no source of the profile"
	done < <(jqv '.. | objects | .source_refs? // empty | .[]' | sort -u)

	# And the profile's source has to be one of those in the frontmatter. Otherwise the agronomy cites
	# a document the page does not declare, and the page's provenance stops covering its doses.
	while IFS= read -r ref; do
		[ -n "$ref" ] || continue
		printf '%s\n' "$fm" | grep -q "resource: \"$ref\"" ||
			err "$p" "the profile cites '$ref', which is not in the frontmatter's 'sources'"
	done < <(jqv '.sources[]?.ref' | sort -u)

	# The registration list lives once, in the frontmatter's certified_crops, in the datasheet's
	# words; it resolves to ids through the crops leaf. The profile does not repeat it: an agricultural
	# product says all_crops, because it works on any crop, and the registration reaches as far as the
	# datasheet reaches. Only a listed_crops_only profile, the one that really does not work outside
	# its list, writes crops, and there it does have to say the same as the frontmatter, because they
	# are two copies of the same fact and two copies nobody compares diverge at the first correction.
	local cert_list cert_scalar profile_crops
	cert_list="$(fm_list "$p" certified_crops | resolve crops | sort -u)"
	cert_scalar="$(printf '%s\n' "$fm" | sed -n 's/^certified_crops: *//p')"
	profile_crops="$(jqv '.crops[]?' | sort -u)"
	if [ -n "$cert_list" ] && [ "$scope" = listed_crops_only ]; then
		[ "$cert_list" = "$profile_crops" ] ||
			err "$p" "the profile's 'crops' does not say the same as the frontmatter's 'certified_crops'"
	elif [ "$cert_scalar" = all_crops ]; then
		[ "$scope" = all_crops ] ||
			err "$p" "'certified_crops: all_crops' and the profile says crop_scope '$scope'"
	fi

	# An override for a crop where the product is not certified does not fail: it never matches.
	# It is a regimen someone wrote, that reads as current and is never applied.
	#
	# Matching on a concept higher up is valid, and it is the normal case: Floral's datasheet gives
	# its dose "on ornamentals" and the product is certified on flowers and foliage, which hang from
	# there. That is why the comparison is against the profile's crops PLUS all their ancestors, and
	# not against the flat list. Comparing flat turns the right way of writing an override into an error.
	if [ "$scope" = listed_crops_only ]; then
		local reachable
		reachable="$(printf '%s\n' "$profile_crops" | awk -F'\t' -v e=crops '
			NR == FNR { if ($1 == e) parent[$2] = $3; next }
			{ c = $0; while (c != "") { print c; c = parent[c] } }
		' <(printf '%s\n' "$PARENTS") - | sort -u)"
		while IFS= read -r c; do
			[ -n "$c" ] || continue
			printf '%s\n' "$reachable" | grep -qxF -- "$c" ||
				err "$p" "an override matches '$c', which no crop of the product reaches"
		done < <(jqv '.overrides[]?.match.crops[]?' | sort -u)
	fi

	# Two regimens with the same id in the same list: nobody can say which one a correction refers
	# to, and the module does not look at them.
	local repeated
	repeated="$(jqv '[.default_regimens[]?.id] | .[]' | sort | uniq -d)"
	[ -z "$repeated" ] && repeated="$(jqv '.overrides[]? | [.regimens[]?.id] | .[]' | sort | uniq -d)"
	[ -n "$repeated" ] && err "$p" "there are regimens with a repeated id: $(printf '%s' "$repeated" | tr '\n' ' ')"
	return 0
}

# The floor the OKF SPEC (§11) asks of any document in the bundle. Returns 1 if the page cannot be
# read, and leaves the frontmatter in $FM for whoever wants to keep checking it.
conformance() {
	local p="$1"
	FM=""
	if [ "$(head -1 "$p")" != '---' ]; then
		err "$p" "does not open with frontmatter"
		return 1
	fi
	# The closing is looked for as an exact '---' line after the first. The old form compared the
	# frontmatter against the rest of the file, and since command substitution eats trailing
	# newlines, unclosed frontmatter passed in almost every form.
	#
	# It goes in a single awk and not in 'sed | grep -q' on purpose. There grep exits as soon as it
	# finds the line, sed dies with SIGPIPE, and 'pipefail' returns that 141 as the pipeline's state:
	# the well-formed file is reported as broken. It depends on whether what sed still has to write
	# fits in the pipe buffer, so it shows up with long files and comes and goes with the machine's
	# load. With FORMAT.md, 18k, it trips once in many.
	if ! awk 'NR > 1 && $0 == "---" { closed = 1; exit } END { exit !closed }' "$p"; then
		err "$p" "the frontmatter does not close"
		return 1
	fi
	local fm
	fm="$(awk 'NR > 1 { if ($0 == "---") exit; print }' "$p")"
	if ! printf '%s\n' "$fm" | grep -qE '^type:[[:space:]]*[^[:space:]]'; then
		err "$p" "no 'type:' in the frontmatter, or empty"
		return 1
	fi
	# The SPEC asks for *parseable* frontmatter, and this is not a YAML parser. It checks the one way
	# of breaking it that writes itself: a ':' followed by a space inside an unquoted value. It reads
	# perfectly and does not parse, so it cannot be found by eye.
	#
	# Values that open with a quote and those that open with '{' or '[' are left out, because there
	# the ':' inside is part of a flow collection and is legal: 'generated: { by: x, at: y }' is the
	# form the SPEC itself uses. \042 \047 \173 \133 are " ' { [, written this way so as not to fight
	# with shell quoting.
	local dirty
	dirty="$(awk 'NR > 1 {
		if ($0 == "---") exit
		if ($0 !~ /^[A-Za-z_][A-Za-z0-9_]*:[ \t]+/) next
		key = $0; sub(/:.*/, "", key)
		value = $0; sub(/^[A-Za-z_][A-Za-z0-9_]*:[ \t]+/, "", value)
		if (value !~ /^[\042\047\173\133]/ && value ~ /:[ \t]/) { print key; exit }
	}' "$p")"
	if [ -n "$dirty" ]; then
		err "$p" "'$dirty:' has a ':' in an unquoted value and the YAML does not parse"
		return 1
	fi
	# 'generated' is optional in the SPEC and mandatory here. Without it there is no way to look at a
	# page and know whether it is the skeleton ingest.sh wrote or something a person curated, and that
	# distinction is what all the work in the repo rests on. Until today it lived in an HTML comment.
	# The compact form '{ by: x, at: y }' reads the same as the §5.2 list, which appears as soon as a
	# person writes a page and an agent classifies it later: they are two producers of the same
	# document and squashing them into one makes the frontmatter state something that did not happen.
	local gen
	gen="$(printf '%s\n' "$fm" | awk '/^generated:/ { f = 1; print; next } f && /^[[:space:]]/ { print; next } f { f = 0 }')"
	if [ -z "$gen" ]; then
		err "$p" "no 'generated:' in the frontmatter"
		return 1
	fi
	case "$gen" in
	*by:*at:*) ;;
	*) err "$p" "'generated:' needs 'by' and 'at'"; return 1 ;;
	esac
	local generated_actors
	generated_actors="$(actors "$gen")"
	if [ -z "$generated_actors" ]; then
		err "$p" "'generated:' without 'by'"
		return 1
	fi
	while IFS= read -r a; do
		[ -n "$a" ] || continue
		actor_ok "$a" || err "$p" "the 'by' of generated does not follow §7: '$a'"
	done <<<"$generated_actors"

	# The three tiers of §5.3, which are derived from 'verified' and not stored: without the key the
	# page is unverified, with an actor that is not 'human:' it is machine-confirmed, and with one
	# that is, it is human-reviewed. They are counted for the dashboard, not required: not having
	# 'verified' is a data point.
	local ver
	ver="$(printf '%s\n' "$fm" | awk '/^verified:/ { f = 1; print; next } f && /^[[:space:]]/ { print; next } f { f = 0 }')"
	if [ -n "$ver" ]; then
		local verified_actors
		verified_actors="$(actors "$ver")"
		if [ -z "$verified_actors" ]; then
			err "$p" "'verified:' without 'by'"
		elif ! printf '%s\n' "$ver" | grep -q 'at:'; then
			err "$p" "'verified:' without 'at'; §5.2 asks for both"
		else
			while IFS= read -r a; do
				[ -n "$a" ] || continue
				actor_ok "$a" || err "$p" "the 'by' of verified does not follow §7: '$a'"
			done <<<"$verified_actors"
		fi
	fi
	case "$ver" in
	*human:*) reviewed=$((reviewed + 1)) ;;
	*by:*) machine=$((machine + 1)) ;;
	esac

	FM="$fm"
	return 0
}

# --- links and catalog ---------------------------------------------------------------------------
#
# A broken markdown link fails nowhere: it looks just like a good one until someone clicks it. And
# in company.md the link IS the product list, so a product named without a page stops being an
# invisible oversight. Syntax examples do not count, so fenced blocks and whatever sits in backticks
# are skipped: FORMAT.md writes '[Title](path)' to explain the format of an index, and that is not
# a link to anywhere.
links() {
	local f d t dest
	while IFS= read -r f; do
		d="$(dirname "$f")"
		while IFS= read -r t; do
			[ -n "$t" ] || continue
			case "$t" in
			http://* | https://* | mailto:* | \#*) continue ;;
			esac
			dest="${t%%#*}"
			[ -n "$dest" ] || continue
			[ -e "$d/$dest" ] || err "$f" "broken link: '$t'"
		done < <(awk '/^```/ { f = !f; next } !f' "$f" | sed 's/`[^`]*`//g' |
			grep -oE '\]\([^)]+\)' | sed 's/^](//; s/)$//')
	done < <(find . -mindepth 1 \( -name '.*' -o -name raw \) -prune -o -name '*.md' -print |
		sed 's|^\./||' | sort)
}

# The other direction. A new page the catalog does not name exists and does not sell: that is how
# Molibdato de Sodio got lost, which had a page, a datasheet and tags from day one and was not in
# company.md.
catalog() {
	local cat=company_info/company.md linked pages p
	[ -f "$cat" ] || return 0
	linked="$(grep -oE '\]\(\.\./'"$PAGES"'/[a-z0-9-]+\.md\)' "$cat" |
		sed "s|](\.\./$PAGES/||; s|\.md)||" | sort -u)"
	pages="$(ls "$PAGES"/*.md | sed "s|$PAGES/||; s|\.md$||" | grep -v '^index$' | sort)"
	while IFS= read -r p; do
		[ -n "$p" ] || continue
		printf '%s\n' "$linked" | grep -qxF -- "$p" ||
			err "$PAGES/$p.md" "exists and the catalog in company.md does not name it"
	done <<<"$pages"
}

# --- the business rules of company_info/ ---------------------------------------------------------
#
# The shipping numbers were written five times in prose across two files and nothing compared them.
# The day the courier raises the rate, whoever updates it will change four of the five and the
# others will keep answering the old price, with nothing warning about it. From now on the
# '# Rules' block rules and the prose has to match it.
shipping_rules() {
	local p=company_info/shipping.md json fences amounts f m
	[ -f "$p" ] || return 0
	if ! grep -q '^# Rules$' "$p"; then
		err "$p" "has no '# Rules'; the shipping amounts live in that block"
		return 1
	fi
	if [ "$NO_JQ" = 1 ]; then
		err "$p" "jq is needed to check the rules block and it is not installed"
		return 1
	fi
	fences="$(awk '/^# Rules$/ { f = 1; next } /^# / { f = 0 } f && /^```json$/ { n++ } END { print n + 0 }' "$p")"
	if [ "$fences" != 1 ]; then
		err "$p" "'# Rules' has $fences json blocks and only the first is read"
		[ "$fences" = 0 ] && return 1
	fi
	json="$(awk '/^# Rules$/ { f = 1; next } f && /^```json$/ { g = 1; next } g && /^```$/ { exit } g' "$p")"
	if ! printf '%s' "$json" | jq -e . >/dev/null 2>&1; then
		err "$p" "the rules block is not valid JSON"
		return 1
	fi
	[ "$(printf '%s' "$json" | jq -r '.schema // ""')" = "company/shipping/v1" ] ||
		err "$p" "the rules block declares another schema"

	# Every amount in quetzales that the prose of company_info/ writes has to be a number in the
	# block. Two truths written separately diverge, and the one read first wins. The check is
	# deliberately blunt and also reaches the examples: an example with an invented figure reads just
	# like a rate, so an example is written with no figure or with the block's.
	amounts="$(printf '%s' "$json" | jq -r '[.. | numbers] | .[]' | sort -u)"
	for f in company_info/*.md; do
		while IFS= read -r m; do
			[ -n "$m" ] || continue
			printf '%s\n' "$amounts" | grep -qxF -- "$m" ||
				err "$f" "says Q$m and the rules block in shipping.md does not have that number"
		done < <(grep -oE 'Q[0-9][0-9,]*' "$f" | tr -d 'Q,' | sort -u)
	done
}

# The ten account numbers live in the tables and in the block. A digit dropped in a table sends the
# transfer nowhere, the customer believes they paid and nobody finds out until someone complains.
# The two copies have to say the same, in both directions.
collection_rules() {
	local p=company_info/bank-accounts.md json fences block tables n
	[ -f "$p" ] || return 0
	if ! grep -q '^# Rules$' "$p"; then
		err "$p" "has no '# Rules'; the accounts live in that block"
		return 1
	fi
	if [ "$NO_JQ" = 1 ]; then
		err "$p" "jq is needed to check the rules block and it is not installed"
		return 1
	fi
	fences="$(awk '/^# Rules$/ { f = 1; next } /^# / { f = 0 } f && /^```json$/ { n++ } END { print n + 0 }' "$p")"
	if [ "$fences" != 1 ]; then
		err "$p" "'# Rules' has $fences json blocks and only the first is read"
		[ "$fences" = 0 ] && return 1
	fi
	json="$(awk '/^# Rules$/ { f = 1; next } f && /^```json$/ { g = 1; next } g && /^```$/ { exit } g' "$p")"
	if ! printf '%s' "$json" | jq -e . >/dev/null 2>&1; then
		err "$p" "the rules block is not valid JSON"
		return 1
	fi
	[ "$(printf '%s' "$json" | jq -r '.schema // ""')" = "company/collection/v1" ] ||
		err "$p" "the rules block declares another schema"

	block="$(printf '%s' "$json" | jq -r '.accounts[]?.number // empty' | sort -u)"
	tables="$(awk -F'|' 'NF >= 4 { gsub(/^ +| +$/, "", $3); if ($3 ~ /^[0-9][0-9-]*$/) print $3 }' "$p" | sort -u)"
	while IFS= read -r n; do
		[ -n "$n" ] || continue
		printf '%s\n' "$block" | grep -qxF -- "$n" ||
			err "$p" "the table lists account $n and the rules block does not have it"
	done <<<"$tables"
	while IFS= read -r n; do
		[ -n "$n" ] || continue
		printf '%s\n' "$tables" | grep -qxF -- "$n" ||
			err "$p" "the rules block lists account $n and no table shows it"
	done <<<"$block"
}

# --- the advisor's rules: governance/ -------------------------------------------------------------
#
# Every question with which the agro advisor decides something by reading text, one file per domain.
# It exists for the same reason as ontology/: two rules that decide the same fact diverge and
# nothing says so. On Oct 2, 2026 the guardian stopped escalating a discontinued product because a
# word of the writer changed, and the turn's case, which already knew it, lived somewhere else.
#
# What can be compared without reading the prose: two rules with the same 'question' or the same
# 'crm_reason' decide the same fact, and one of the two has to declare it in 'same_fact'.
# 'same_fact' points to the FIRST: to an id that exists and does not in turn point to another,
# because a chain hides which rule is in charge. What is in no column, such as the guardian
# repeating the turn's case, is declared by a person.
GOV=governance
gov_domains=0
gov_rules=0

GOV_AWK='
BEGIN { FS = "|"; OFS = "\t" }
function cell(n,   v) { v = $n; gsub(/^[ \t]+|[ \t]+$/, "", v); return v }
function bad(a, m) { printf "ERR\t%s\t%s\n", a, m }
FNR == 1 {
	file = FILENAME
	dom = file; sub(/.*\//, "", dom); sub(/\.md$/, "", dom)
	in_table = 0; warned = 0; dashes = 0; said = ""
	skip = (dom == "index")
	if (!skip) { leaves[file] = dom; ndom++ }
}
skip { next }
$0 == "---" && dashes < 2 { dashes++; next }
dashes == 1 && /^domain:/ { said = $0; sub(/^domain:[ \t]*/, "", said); gsub(/"/, "", said)
	if (said != dom) bad(file, "domain: \"" said "\" and the file is named " dom ".md") ; next }
dashes == 1 && /^schema:/ { s = $0; sub(/^schema:[ \t]*/, "", s)
	if (s != "agro/governance/v1") bad(file, "schema: \"" s "\"; it should be agro/governance/v1") ; next }
dashes == 1 && /^type:/ { t = $0; sub(/^type:[ \t]*/, "", t)
	if (t != "governance") bad(file, "type: \"" t "\"; it should be governance") ; next }
/^\|/ {
	if (cell(2) == "id") {
		h = cell(2) "," cell(3) "," cell(4) "," cell(5) "," cell(6) "," cell(7) "," cell(8) "," cell(9)
		if (h != "id,question,type,reads,threshold,action,crm_reason,same_fact")
			bad(file, "the columns are id | question | type | reads | threshold | action | crm_reason | same_fact")
		in_table = 1; next
	}
	if (cell(2) ~ /^-+$/) next
	if (!in_table) { if (!warned) { bad(file, "there is a table before the rules table"); warned = 1 }; next }
	id = cell(2)
	if (id == "") next
	if (index(id, dom "/") != 1 || length(id) <= length(dom) + 5 || id !~ /_tag$/) bad(file, "the id \"" id "\" is not " dom "/<rule>_tag")
	if (id in file_of) { bad(file, "duplicate id \"" id "\" (also in " file_of[id] ")"); next }
	file_of[id] = file; position[++n] = id; nrules++
	asked[id] = cell(3); type = cell(4); thr = cell(6); reason[id] = cell(8); same[id] = cell(9)
	if (asked[id] == "") bad(file, id ": no question")
	if (type != "noul" && type != "choice" && type != "code") bad(file, id ": type \"" type "\"; it should be noul, choice or code")
	if (type == "code") { if (thr != "") bad(file, id ": a code rule takes no threshold") }
	else if (thr != "argmax" && !(thr ~ /^(0(\.[0-9]+)?|1(\.0+)?)$/)) bad(file, id ": threshold \"" thr "\"; it should be a number between 0 and 1 or argmax")
}
END {
	for (i = 1; i <= n; i++) has[file_of[position[i]]]++
	for (a in leaves) if (has[a] == 0) bad(a, "the domain declares no rules")
	for (i = 1; i <= n; i++) {
		id = position[i]
		m = split(same[id], ts, ",")
		for (j = 1; j <= m; j++) {
			t = ts[j]; gsub(/^[ \t]+|[ \t]+$/, "", t)
			if (t == "") continue
			declared[id SUBSEP t] = 1
			if (t == id) { bad(file_of[id], id ": same_fact points to itself"); continue }
			if (!(t in file_of)) { bad(file_of[id], id ": same_fact points to \"" t "\", which does not exist"); continue }
			if (same[t] != "") bad(file_of[id], id ": same_fact points to \"" t "\", which points to another; it should be the first")
		}
	}
	for (i = 1; i <= n; i++) for (j = i + 1; j <= n; j++) {
		a = position[i]; b = position[j]
		if ((a SUBSEP b) in declared || (b SUBSEP a) in declared) continue
		if (asked[a] != "" && asked[a] == asked[b])
			bad(file_of[b], b ": question \"" asked[b] "\" same as " a ", not declared in same_fact")
		else if (reason[a] != "" && reason[a] == reason[b])
			bad(file_of[b], b ": crm_reason \"" reason[b] "\" same as " a ", not declared in same_fact")
	}
	printf "N\t%d\t%d\n", ndom, nrules
}'

governance() {
	local output file message
	[ -d "$GOV" ] || return 0
	ls "$GOV"/*.md >/dev/null 2>&1 || return 0
	output="$(awk "$GOV_AWK" "$GOV"/*.md)"
	gov_domains="$(printf '%s\n' "$output" | awk -F'\t' '$1 == "N" { print $2 }')"
	gov_rules="$(printf '%s\n' "$output" | awk -F'\t' '$1 == "N" { print $3 }')"
	while IFS="$(printf '\t')" read -r _ file message; do
		[ -n "$file" ] || continue
		err "$file" "$message"
	done < <(printf '%s\n' "$output" | grep '^ERR	')
}

vocabulary

if [ $# -gt 0 ]; then
	files=("$@")
else
	files=("$PAGES"/*.md)
	# The rest of the bundle. Hidden directories and raw/ are skipped: .claude/skills/*.md are
	# instructions for the agent and raw/ holds the source PDFs, neither is a bundle page.
	while IFS= read -r other; do
		files+=("${other#./}")
	done < <(find . -mindepth 1 \( -name '.*' -o -name raw -o -name "$PAGES" \) -prune -o \
		-name '*.md' -print | sort)
fi

for p in "${files[@]}"; do
	p="${p#./}"
	[ -f "$p" ] || continue
	# index.md and log.md are reserved names of the SPEC: they are not concept documents and carry no
	# frontmatter, except the okf_version of the root index.md.
	case "$(basename "$p")" in
	index.md | log.md) continue ;;
	esac

	# Outside products/ only the conformance floor is asked. A company_info page is prose, it has
	# neither the section vocabulary nor presentations to curate.
	case "$p" in
	"$PAGES"/*) ;;
	*)
		others=$((others + 1))
		conformance "$p"
		continue
		;;
	esac

	pages=$((pages + 1))
	missing=""

	# --- that it can be read ---

	conformance "$p" || continue
	fm="$FM"
	for k in title normalized_name wiki_id state; do
		printf '%s\n' "$fm" | grep -q "^$k:" || err "$p" "missing '$k:' in the frontmatter"
	done

	# 'state' is a closed vocabulary of four values. Empty means "not declared" and is valid; a
	# fifth value is not. It is checked here and not in ontology/ because it is not an axis of
	# concepts that gets curated, but a SPEC field with a fixed list.
	#
	# It matters because of what does NOT happen when it is misspelled. The reader stores
	# 'discontinuated' as a string and does not complain, but the rule below compares against
	# 'discontinued' and does not apply: the page becomes quotable again without anyone deciding so.
	state="$(printf '%s\n' "$fm" | sed -n 's/^state:[[:space:]]*//p' | tr -d '"' | head -1)"
	case "$state" in
	"" | current | out_of_stock | discontinued | withdrawn) ;;
	*) err "$p" "state: '$state' is not current, out_of_stock, discontinued or withdrawn" ;;
	esac

	# Only the headings BEFORE "# Datasheet" are checked: from there down the reader treats any
	# reserved heading as datasheet content, which is exactly what is wanted.
	while IFS= read -r h; do
		[ -n "$h" ] || continue
		name="${h#\# }"
		case " $SECTIONS " in
		*" $name "*) ;;
		*) err "$p" "unknown section: '$name'" ;;
		esac
	done < <(sed -n '/^# Datasheet$/q;/^# /p' "$p")

	grep -q '^# Datasheet$' "$p" || err "$p" "has no '# Datasheet'"

	# Provenance lives in the frontmatter's 'sources'. "# Citations" in the body is the v0.1 form the
	# SPEC retired: a consumer that only reads 'sources' sees none of what it says.
	grep -q '^# Citations$' "$p" && err "$p" "has '# Citations'; provenance goes in 'sources'"

	# The page's terms against the vocabulary. A country that does not resolve does not fail loudly:
	# the equivalent is left without an owner and the product stops being found by its local name,
	# which is the only reason the table exists. Whoever asks for BROQUEL does not get to ESCUDO.
	check_terms "$p" countries "country" < <(awk '/^# Equivalents$/ { f = 1; next } /^# / { f = 0 } !f { next } /^\|/ {
		split($0, c, "|"); v = c[2]
		gsub(/^[ \t]+|[ \t]+$/, "", v)
		if (v == "" || v == "Country" || v ~ /^-+$/) next
		print v
	}' "$p")
	check_ids "$p" product-types "product type" < <(fm_list "$p" tags)

	# certified_crops is the list of crops where the product is CERTIFIED, not where it works.
	# Products work on any of them; the registration's backing reaches as far as the datasheet
	# reaches, and that list is the only place in the bundle where that fact is written. The term goes
	# exactly as the datasheet writes it: the day a concept splits into varieties, the term re-resolves
	# by itself to the new one, and an archived id would already have lost the precision.
	#
	# 'all_crops' and 'not_applicable' are the other two values, with the same vocabulary crop_scope
	# uses in the agronomic profile, so as not to have two words for the same idea.
	case "$(printf '%s\n' "$fm" | grep '^certified_crops:')" in
	"certified_crops: all_crops" | "certified_crops: not_applicable" | "certified_crops:") ;;
	"") ;;
	*) err "$p" "scalar 'certified_crops:' has to be all_crops or not_applicable" ;;
	esac
	check_terms "$p" crops "certified crop" < <(fm_list "$p" certified_crops)

	agronomy "$p" "$fm"

	# The only mandatory thing in a sources entry is 'resource'. Without a path the source cannot be
	# followed, and a citation that cannot be followed is worse than none: it looks like the data is audited.
	src="$(printf '%s\n' "$fm" | awk '/^sources:$/ { f = 1; next } f && /^[^[:space:]]/ { f = 0 } f')"
	entries="$(printf '%s\n' "$src" | grep -c '^[[:space:]]*- ')"
	resources="$(printf '%s\n' "$src" | grep -c 'resource:')"
	if [ "$entries" -eq 0 ]; then
		err "$p" "no 'sources:' in the frontmatter"
	elif [ "$entries" -ne "$resources" ]; then
		err "$p" "sources has $entries entries and $resources 'resource:'; one is missing"
	fi

	# --- what is left to curate ---

	# While 'generated.by' is still ingest.sh, the page is the raw skeleton: nobody looked at the OCR
	# or gave it a tag. It is the pending item that contains all the others.
	case "$fm" in
	*"by: process:ingest.sh"*)
		missing="$missing curation"
		uncurated=$((uncurated + 1))
		;;
	esac
	if [ -z "$(fm_list "$p" tags)" ]; then
		missing="$missing tags"
		no_tags=$((no_tags + 1))
	fi
	# A page without the key declared nothing; one with 'not_applicable' declared that it does not
	# apply. They are different and the second is not a pending item.
	if ! printf '%s\n' "$fm" | grep -q '^certified_crops:'; then
		missing="$missing certified-crops"
		no_certified=$((no_certified + 1))
	fi
	rows="$(awk '/^# Presentations$/ { f = 1; next } /^# / { f = 0 } f && /^\| *[0-9]/ { n++ } END { print n + 0 }' "$p")"
	case "$state" in
	discontinued | withdrawn)
		# A product no longer sold is not quoted. The page stays, because it keeps being named in
		# conversations, but with a price it returns to the catalog through the back door: whoever
		# answers "how much is it?" reads the table, not the frontmatter.
		#
		# 'out_of_stock' stays out of this on purpose: it will be back, and its price is the one it
		# has when it returns.
		[ "$rows" = 0 ] ||
			err "$p" "state: $state with $rows price row(s); what is not sold is not quoted"
		# And the other way around: its empty table stops being pending. It is not missing data, it is
		# the decision not to load it, and counting it put four pages on the work list forever. A
		# list of pending items that never goes down stops being read, and with it the real ones.
		;;
	*)
		if [ "$rows" = 0 ]; then
			missing="$missing presentations"
			no_prices=$((no_prices + 1))
		fi
		;;
	esac
	if ! grep -q '^# Agronomy$' "$p"; then
		missing="$missing agronomy"
		no_agro=$((no_agro + 1))
	fi
	[ -n "$missing" ] && printf 'pending  %-34s missing:%s\n' "$(basename "$p")" "$missing"
done

links
catalog
shipping_rules
collection_rules
governance

echo
printf 'pages: %d · other documents: %d · errors: %d\n' "$pages" "$others" "$errors"
printf 'vocabulary: %d axes · %d concepts\n' "$axes" "$concepts"
printf 'governance: %d domains · %d rules\n' "$gov_domains" "$gov_rules"
printf 'no tags: %d · no certified crops: %d · no presentations: %d · no agronomy: %d · uncurated: %d\n' \
	"$no_tags" "$no_certified" "$no_prices" "$no_agro" "$uncurated"
printf 'reviewed by a person: %d · confirmed by a process: %d · unverified: %d\n' \
	"$reviewed" "$machine" "$((pages + others - reviewed - machine))"
if [ "$vocab_broken" -ne 0 ]; then
	echo
	echo 'the vocabulary does not load, so the pages were NOT checked against it: fix the leaves first'
fi
[ "$errors" -eq 0 ] || exit 1
