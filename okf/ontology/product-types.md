---
type: ontology
schema: wiki/ontology/v1
axis: product-types
label: "Product types"
generated: { by: claude-code/claude-opus-5, at: 2026-08-27T07:36:23Z }
---

The tags a page is classified with. It is the tenant's vocabulary: what is not here is not a new
type, it is a misspelled tag.

## Five facets, not a hierarchy

The obvious agrochemical taxonomy does not work for this catalog. Almost everything is biological,
and BIOMET 70 EW is insecticide, microbial and approved for organic at the same time. Forcing it to
choose which of the three is "the" type loses the other two.

The manufacturer already classifies itself with two vocabularies at once, and it shows in the first
line of each datasheet: a functional one, "microbial insecticide", and a registration one,
"fertilizer-related substance". They are different axes and here they go separately.

The five roots are facets, not families. **A page carries one tag per facet that applies to it**, and
no facet is mandatory: an adjuvant has no control function and an insecticide has no nutritional
role.

`function` answers what it controls. `nature`, what it is made of. `role`, what it is for beyond
controlling. `registration`, under what category it is registered. `suitability`, in what management
it can be used.

It goes in prose and not in a table on purpose: a leaf carries **one single** table, the concepts
table. The reader starts consuming rows at the first one it finds, so an explanatory table up here
would be read as five concepts with ids in backticks.

Roots being facets has a wart: `insecticide` hangs from `function`, so asking whether an insecticide
"is a function" gives yes. It bothers nobody and in exchange expanding `function` returns the whole
facet.

## What stayed an alias and not a concept

Each datasheet gives itself its own title: Fillvane K is a "fruit sizer", Vigor a "vigor booster",
Sproutvane a "root revitalizer", Leafvane Amin an "anti-stress". Almost all of them appear in a single
product. Turning them into concepts would make a list of marketing synonyms with one row per page,
which classifies nothing.

The cut is whether they name a function someone really asks for. "Rooter" and "fruit sizer" do, and
they are concepts. "Vigor booster" and "revitalizer" are ways of saying biostimulant, and they are
aliases.

`zero days to harvest` is not here even though eleven datasheets say it. It is a period, not a type,
and it goes in the agronomic profile where it can be compared with a number.

`ipm-approved` says "integrated management" and not "integrated pest management" because Wardvane
and Trico, the two fungicides, write "integrated disease management". It is the same practice and
whoever filters by IPM wants to see them. Splitting it in two would have made a two-page concept
nobody looks up.

| id | label | parent | alias | note |
|---|---|---|---|---|
| function | Function |  | control function | facet: what it controls |
| insecticide | Insecticide | function |  |  |
| acaricide | Acaricide | function | miticide |  |
| nematicide | Nematicide | function |  |  |
| fungicide | Fungicide | function |  |  |
| rodenticide | Rodenticide | function | raticide |  |
| nature | Nature |  |  | facet: what it is made of |
| microbial | Microbial | nature | biological, microbiological | thirteen products |
| entomopathogen | Entomopathogen | microbial | entomopathogens, entomopathogenic fungus | eight, the ones that infect the insect |
| mycorrhiza | Mycorrhiza | microbial | mycorrhizae, mycorrhizas, mycorrhizal, recover, recovers, recovery, recovering | the customer asks for it as "something to help the plant recover" |
| botanical | Botanical | nature | plant extract, algae extract |  |
| mineral | Mineral | nature |  |  |
| role | Role |  |  | facet: what it is for beyond controlling |
| nutrition | Nutrition | role | nutritional, fertilizer |  |
| foliar-fertilizer | Foliar fertilizer | nutrition | foliar and soil fertilizer |  |
| soil-conditioner | Soil conditioner | nutrition | conditioner, soil improver |  |
| biofertilizer | Biofertilizer | nutrition | inoculant, microbial inoculant | nutrition supplied by a microorganism, not a salt |
| nitrogen-fixer | Nitrogen fixer | biofertilizer | fixer, nitrogen fixers |  |
| solubilizer | Solubilizer | biofertilizer | phosphorus solubilizer, solubilization |  |
| biostimulant | Biostimulant | role | stimulant, vigor booster, revitalizer, anti-stress, hormone complex |  |
| rooter | Rooter | biostimulant | root revitalizer, rooting agent |  |
| fruit-sizer | Fruit sizer | biostimulant |  |  |
| adjuvant | Adjuvant | role | adjuvants, coadjuvant |  |
| sticker | Sticker | adjuvant | sticking agent |  |
| penetrant | Penetrant | adjuvant | silicone adjuvant |  |
| dispersant | Dispersant | adjuvant |  |  |
| emulsifier | Emulsifier | adjuvant | emulsifying agent |  |
| encapsulant | Encapsulant | adjuvant |  |  |
| hardness-corrector | Hardness corrector | adjuvant | water hardness corrector |  |
| physical-control | Physical control | role |  |  |
| trap | Trap | physical-control | traps, monochromatic trap, ethological control |  |
| adhesive | Adhesive | physical-control | glue, organic glue |  |
| bioremediation | Bioremediation | role | bioremediator |  |
| raw-material | Raw material | role | technical grade, technical input | sold as an input, not as a formulation |
| registration | Registration |  |  | facet: under what category it is registered |
| fertilizer-related | Fertilizer-related substance | registration |  |  |
| pesticide-related | Pesticide-related substance | registration |  |  |
| suitability | Suitability |  |  | facet: in what management it can be used |
| organic-approved | Approved for organic farming | suitability | organic, organic farming | fifteen datasheets declare it |
| ipm-approved | Approved for integrated management | suitability | ipm, integrated management, integrated pest management, integrated disease management | thirteen datasheets. Two say "disease" and it is the same practice |
