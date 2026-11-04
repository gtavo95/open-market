---
type: ontology
schema: wiki/ontology/v1
axis: targets
label: "Control targets"
generated: { by: claude-code/claude-opus-5, at: 2026-08-27T07:05:54Z }
---

The pests and diseases a product is recommended against. This is the axis where the business risk
is: products work on any crop, but not against any pest, so getting it wrong here means recommending
something that does not control what the customer has.

Almost all of it came from the datasheets, which already write it in the form needed: common name and
scientific name in parentheses. The alias is what joins the two ends. The datasheet says
`Bemisia tabaci`, the customer says whitefly, and both have to land on the same row.

**The parent is where the datasheet put it.** When the same common name appears with several species
(aphid with three, thrips with two, root rot with two different genera) the common name is the parent
and the species hang from it. That way a query for aphid reaches all three and a page that filed
`Brevicoryne brassicae` is still found.

That is why the generic common name goes as an alias **only on the parent**. An alias that resolves
to two concepts gives no error anywhere: it makes aphid sometimes one thing and sometimes another
depending on the order the file was read in.

Eighteen pages declare targets: the microbials, the rodenticide, five nutritionals and Stickvane.
The five came in when curating the agronomy and refute what this leaf said before, that only the
microbials name the axis. Fillvane, Leafvane Ca-B, Leafvane Fe-Mg-Zn and the two irons write "prevents and
corrects deficiencies of" and an element, and that is a claim about what the product does, just like
"controls whitefly". Whoever asks about iron chlorosis is asking about a target.

Deficiencies are not pests and that is why `target-types` had `deficiency` from the start. What was
missing was here: the `kind` existed and there was no concept for it to point at.

`tick` and the dipterans arrived with Vetvane, the veterinary product, and they are pests that do not
attack a plant. Its datasheet gives them no scientific name, so they are filed as it writes them:
ticks, house fly, paleta fly. Giving them the species one assumes would be inventing the fact the
datasheet does not give.

## The twenty-one Stickvane added

The trap is the product with the most targets in the catalog, and it declares them by color: each
color reflects a wavelength and attracts a different group. The data was in the datasheet's images,
which the OCR lost, and it was recovered by extracting the JPEGs from the PDF.

It brought half the dipterans in this leaf. Four are stable and dairy flies, which is the use the
datasheet gives the white and blue cloths, and with scientific names, something Vetvane does not give.

Three decisions someone will want to argue about:

`stable-fly` (Stomoxys calcitrans) is almost certainly the same insect as `paleta-fly`, the name
Vetvane writes it with. They stay as two concepts because merging them requires asserting a species
the Vetvane datasheet does not give. Whoever confirms the equivalence deletes one and passes its alias
to the other.

`coleoptera` gets in because the datasheet writes "Coleoptera Spp" and what it says has to be filed.
It is a grouping by order and it crosses `borers`, which groups by habit: the pepper weevil is both
and this leaf only admits one parent. It stayed under `borers`, which is how whoever sells looks for
it. A query for coleoptera does not reach it, and that is a debt, not an oversight.

`grain-moths` and `pineapple-tecla` stayed without a parent. The first eats stored grain and not
foliage, so `chewing-pests` would describe it badly. The second bores into the pineapple fruit, but
the datasheet does not say so and hanging it from `borers` would add the missing fact.

| id | label | parent | alias | note |
|---|---|---|---|---|
| sucking-pests | Sucking pests |  | sucking pest, sucking insects | they feed on sap. Our grouping, the datasheet does not name it |
| whitefly | Whitefly | sucking-pests | whiteflies, white fly, bemisia tabaci, aleyrodidae |  |
| aphid | Aphid | sucking-pests | aphids, aphididae |  |
| aphis-gossypii | Aphis gossypii | aphid | cotton aphid |  |
| myzus | Myzus | aphid | myzus spp. | the datasheet does not go below genus |
| brevicoryne-brassicae | Brevicoryne brassicae | aphid | mealy cabbage aphid, cabbage aphid |  |
| thrips | Thrips | sucking-pests | little elongated bugs, elongated bugs, elongated insects, silver spots, silvery leaf, silvery | the customer describes it by the symptoms: elongated bugs and silver spots on the leaf |
| thrips-tabaci | Thrips tabaci | thrips | onion thrips |  |
| frankliniella | Frankliniella | thrips | frankliniella spp. | Stickvane does not go below genus |
| frankliniella-occidentalis | Frankliniella occidentalis | frankliniella | western flower thrips |  |
| paratrioza | Paratrioza | sucking-pests | paratrioza cockerelli | psyllid. The datasheet uses the old genus; the accepted one today is Bactericera |
| diaphorina | Diaphorina | sucking-pests | diaphorina citri | citrus psyllid |
| spittlebug | Spittlebug | sucking-pests | aeneolamia postica, froghopper, mosca pinta |  |
| aeneolamia-contigua | Aeneolamia contigua | spittlebug |  | the second species of the genus a datasheet names |
| chewing-pests | Chewing pests |  | chewing pest, worms | our grouping |
| fall-armyworm | Fall armyworm | chewing-pests | spodoptera frugiperda, armyworm |  |
| borers | Borers |  | borer | our grouping |
| avocado-borer | Avocado borer | borers | stenoma catenifer, avocado seed moth |  |
| black-banana-weevil | Black banana weevil | borers | cosmopolites sordidus, black weevil, banana weevil |  |
| coffee-berry-borer | Coffee berry borer | borers | hypothenemus hampei, broca |  |
| pepper-weevil | Pepper weevil | borers | anthonomus eugenii |  |
| palm-borer | Palm borer | borers | sagalassa valida |  |
| coconut-white-scale | Coconut white scale |  | parlagena bennetti | no parent on purpose. The datasheet calls it a scale, but Parlagena bennetti is a cerambycid. It is filed as the datasheet writes it and is not grouped with the sucking pests |
| white-grub | White grub |  | phyllophaga obsoleta, phyllophaga, gallina ciega | soil larva |
| coleoptera | Coleoptera |  | coleoptera spp., beetles | Stickvane's grouping, by order. It crosses borers, which groups by habit |
| grain-moths | Grain moths |  | plodia interpunctella, grain moth | stored-grain pest. It does not hang from chewing-pests, which are the foliage ones |
| pineapple-tecla | Pineapple tecla |  | tecla basilides, strymon basilides | the datasheet gives both names for the same insect |
| durrantia | Durrantia |  | durrantia arcanella | moth. The Stickvane datasheet does not name it; that the red one catches it was confirmed by the company. No parent, like grain-moths |
| diptera | Diptera |  | dipteran, flies | grouping by order. Vetvane opened it without scientific names; Stickvane does give them |
| house-fly | House fly | diptera | musca domestica, housefly |  |
| paleta-fly | Paleta fly | diptera | mosca de la paleta | Vetvane gives it no species. See the stable-fly note |
| stable-fly | Stable fly | diptera | stomoxys calcitrans | probably the same insect as paleta-fly. Without Vetvane's species nobody can merge them |
| horn-fly | Horn fly | diptera | haematobia irritans |  |
| face-fly | Face fly | diptera | musca autumnalis |  |
| fungus-gnat | Fungus gnat | diptera | fungus gnats | the datasheet names it only in English and gives no genus |
| leafminer | Leafminer | diptera | liriomyza huidobrensis, miner, leaf miner |  |
| mosquito | Mosquito | diptera | culicidae, mosquitoes, zancudo |  |
| mites | Mites |  | mite, tetranychus, tetranychus sp. |  |
| red-spider-mite | Red spider mite | mites | tetranychus urticae, spider mite, red mite |  |
| tick | Tick | mites | ticks | a livestock pest, not a crop pest. Vetvane treats it on the pasture so it does not attach to the animal |
| root-knot-nematode | Root-knot nematode |  | meloidogyne, knot nematode, nodule nematode, galls |  |
| meloidogyne-incognita | Meloidogyne incognita | root-knot-nematode |  |  |
| meloidogyne-javanica | Meloidogyne javanica | root-knot-nematode |  |  |
| foliar-fungi | Foliar fungi |  | foliage fungi | our grouping |
| downy-mildew | Downy mildew | foliar-fungi | pseudoperonospora cubensis, woolly mildew |  |
| powdery-mildew | Powdery mildew | foliar-fungi | cenicilla, oidium |  |
| erysiphe-cichoracearum | Erysiphe cichoracearum | powdery-mildew |  |  |
| podosphaera-pannosa | Podosphaera pannosa | powdery-mildew | rose powdery mildew |  |
| anthracnose | Anthracnose | foliar-fungi | colletotrichum gloeosporioides, colletotrichum |  |
| purple-blotch | Purple blotch | foliar-fungi | alternaria porri |  |
| soil-fungi | Soil and vascular fungi |  | soil fungi, root fungi | our grouping |
| wilt | Wilt | soil-fungi | fusarium, fusarium wilt, wilting, marchitamento | marchitamento is how one of the datasheets writes it |
| fusarium-lycopersici | Fusarium oxysporum f. sp. lycopersici | wilt | tomato wilt |  |
| fusarium-phaseoli | Fusarium oxysporum f. sp. phaseoli | wilt | bean wilt |  |
| root-rot | Root rot | soil-fungi | root rots, rotting roots |  |
| pythium-aphanidermatum | Pythium aphanidermatum | root-rot | pythium |  |
| rhizoctonia-solani | Rhizoctonia solani | root-rot | rhizoctonia |  |
| pepper-wilt | Pepper wilt | soil-fungi | phytophthora capsici, phytophthora |  |
| dry-cane | Dry cane | soil-fungi | cephalosporium sacchari |  |
| rodents | Rodents |  | rodent, rodent pest | the datasheet also names Apodemus sylvaticus and Microtus arvalis, European. They are not filed because they do not occur here |
| sewer-rat | Sewer rat | rodents | rattus norvegicus, sewer rats, gray rat, brown rat, norway rat |  |
| roof-rat | Roof rat | rodents | rattus rattus, roof rats, black rat |  |
| mouse | Mouse | rodents | mus musculus, mice, house mouse |  |
| nutrient-deficiencies | Nutrient deficiencies |  | nutrient deficiency, nutritional deficiency, deficiencies | our grouping. Five datasheets say "prevents and corrects deficiencies of" |
| iron-deficiency | Iron deficiency | nutrient-deficiencies | iron chlorosis, iron shortage, lack of iron | two datasheets, and both clarify that it appears in alkaline soil |
| potassium-deficiency | Potassium deficiency | nutrient-deficiencies | potassium shortage |  |
| calcium-deficiency | Calcium deficiency | nutrient-deficiencies | calcium shortage |  |
| boron-deficiency | Boron deficiency | nutrient-deficiencies | boron shortage |  |
| magnesium-deficiency | Magnesium deficiency | nutrient-deficiencies | magnesium shortage |  |
| zinc-deficiency | Zinc deficiency | nutrient-deficiencies | zinc shortage |  |
