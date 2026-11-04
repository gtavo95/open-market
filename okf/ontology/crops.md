---
type: ontology
schema: wiki/ontology/v1
axis: crops
label: "Crops"
generated: { by: claude-code/claude-opus-5, at: 2026-08-27T07:25:20Z }
---

The crops the datasheets name. There are 121 distinct spellings in the dose tables, and a good part
are the same thing written two ways: watermelon, asparagus and papaya each in two spellings, and the
ugly case, pepper in six. Without this leaf those are six different crops forever.

**A list of crops does not say where the product works, it says where it is certified.** Products
work on any crop; the backing of the registration reaches as far as the datasheet does. They are two
different facts and the page states both: `crop_scope: all_crops`, which is the commercial truth, and
`certified_crops` with this list, which is the registration's. The certification is the same in all
eight countries, so there is a single list per product.

That is why the axis has to be complete and not only cover the crops where the dose changes. Each row
here is a fact with legal backing behind it.

**`certified_crops` carries the term exactly as the datasheet writes it, not the id.** If the
datasheet says "Bell Pepper", that is what is filed. The day `pepper` is split into its varieties,
that term re-resolves by itself to the new concept and nothing was lost; if the page had filed
`pepper`, the precision would already have been lost at curation and no tool could recover it.

## How the tree is built

**Commercial use rules at the top and the botanical family below.** Vegetables, fruit trees, grains,
ornamentals and industrial crops are five roots, and the families hang from them. It is the criterion
a customer asks by and the one the price list is ordered by.

`pastures` is a sixth root with no children and came in later, with Vetvane. It is the only veterinary
product in the catalog and its table does not say "crop" but "use": pasture and animal. The pasture
is filed here because it is a treated surface with a per-hectare dose; the animal is not a crop and
does not get in.

Where the datasheet had already grouped, its grouping was respected. The Trico row that says "Tomato,
Pepper, Potato, Eggplant, Black nightshade" is the one that defines `solanaceae`; the Escudo one with
"Zucchini, Güicoy, Cucumber, Chilacayote, Watermelon, Melon" defines `cucurbits`. The families no row
grouped are marked in the note.

A concept has a single parent, and that forces two choices that look odd on purpose:

- **Tobacco hangs from solanaceae and therefore from vegetables**, which it is not. It is chosen this
  way because it shares pests with tomato and pepper, and a query about solanaceae has to reach it.
  Silverstrike lists it next to onion against the same thrips.
- **Sugarcane hangs from industrial crops**, even though botanically it is a grass. It is sold and
  treated as an industrial crop.

In both cases the error is harmless and the alternative broke something that does get queried.

Three terms from the corpus did not get in:

- `home gardening` and `crop seedlings and seedbeds` are not crops. The second is an application
  route and lives in `routes`.
- `tomato tobacco`, `melon watermelon`, `watermelon melon` and `french bean snow pea` are two crops
  the OCR glued into one cell. They are split in two when curated; filing them that way would invent
  a crop.

| id | label | parent | alias | note |
|---|---|---|---|---|
| vegetables | Vegetables |  | vegetable, veggies | one datasheet names it as if it were a crop |
| solanaceae | Solanaceae | vegetables | solanaceous, nightshade family | group from a Trico row |
| tomato | Tomato | solanaceae | tomatoes, jitomate |  |
| tomatillo | Tomatillo | solanaceae | miltomate, husk tomato |  |
| pepper | Pepper | solanaceae | peppers, chile, chili, chile pepper, chili pepper, sweet pepper, bell pepper, jalapeño pepper, jalapeño, capsicum, aji | no datasheet gives jalapeño a different dose from bell pepper. The day one does, it gets split |
| potato | Potato | solanaceae | potatoes |  |
| eggplant | Eggplant | solanaceae | aubergine |  |
| black-nightshade | Black nightshade | solanaceae | nightshade, quilete, hierba mora |  |
| tobacco | Tobacco | solanaceae |  | it is not a vegetable. It hangs from here because it shares pests with tomato and pepper |
| cucurbits | Cucurbits | vegetables | cucurbit, cucurbitaceae, gourd family | group from an Escudo row |
| cucumber | Cucumber | cucurbits | cucumbers |  |
| melon | Melon | cucurbits | melons |  |
| watermelon | Watermelon | cucurbits | watermelons |  |
| pumpkin | Pumpkin | cucurbits | pumpkins, squash, calabaza |  |
| zucchini | Zucchini | cucurbits | zuchini, courgette, calabacita |  |
| summer-squash | Summer squash | cucurbits | guicoy |  |
| fig-leaf-gourd | Fig-leaf gourd | cucurbits | chilacayote |  |
| winter-squash | Winter squash | cucurbits | zapallo |  |
| legumes | Legumes | vegetables | legume | group from a Trico row |
| bean | Bean | legumes | beans, frijol |  |
| green-bean | Green bean | legumes | green beans, string bean, ejote | our grouping. Plain green bean does not say which of the two; expanding it reaches both |
| french-bean | French bean | green-bean | french beans, ejote frances |  |
| snap-bean | Snap bean | green-bean | snap beans, frijol ejotero |  |
| pea | Pea | legumes | peas, garden pea |  |
| snow-pea | Snow pea | legumes | snow peas |  |
| sugar-snap-pea | Sugar snap pea | legumes | sugar snap, sugar snap peas |  |
| broad-bean | Broad bean | legumes | fava bean, fava |  |
| peanut | Peanut | legumes | peanuts, groundnut |  |
| soybean | Soybean | legumes | soy, soya |  |
| lentil | Lentil | legumes | lentils |  |
| alfalfa | Alfalfa | legumes |  |  |
| crucifers | Crucifers | vegetables | crucifer, brassicas, brassicaceae | our grouping |
| broccoli | Broccoli | crucifers |  |  |
| cauliflower | Cauliflower | crucifers |  |  |
| cabbage | Cabbage | crucifers | cabbages |  |
| brussels-sprouts | Brussels sprouts | crucifers | brussels sprout |  |
| radish | Radish | crucifers | radishes |  |
| apiaceae | Apiaceae | vegetables | apiaceous, umbellifers | group from a Wardvane row |
| carrot | Carrot | apiaceae | carrots |  |
| celery | Celery | apiaceae |  |  |
| parsley | Parsley | apiaceae |  |  |
| cilantro | Cilantro | apiaceae | coriander, culantro |  |
| fennel | Fennel | apiaceae |  |  |
| dill | Dill | apiaceae |  |  |
| anise | Anise | apiaceae |  |  |
| chenopods | Chenopods | vegetables | chenopod, chenopodiaceae | one datasheet names it as if it were a crop |
| spinach | Spinach | chenopods |  |  |
| chard | Chard | chenopods | swiss chard |  |
| beet | Beet | chenopods | beets, beetroot |  |
| alliums | Alliums | vegetables | allium, liliaceae | our grouping |
| onion | Onion | alliums | onions |  |
| green-onion | Green onion | alliums | green onions, scallion, scallions, spring onion, cebollin |  |
| garlic | Garlic | alliums |  |  |
| lettuce | Lettuce | vegetables | lettuces | no intermediate family: it is the only one of its family in the catalog |
| asparagus | Asparagus | vegetables |  | no intermediate family |
| artichoke | Artichoke | vegetables | artichokes | no intermediate family |
| okra | Okra | vegetables |  | no intermediate family |
| fruit-trees | Fruit trees |  | fruit tree, fruit crops | named by the Floral datasheet |
| citrus | Citrus | fruit-trees | citrus fruit | one datasheet names it as if it were a crop |
| orange | Orange | citrus | oranges |  |
| lemon | Lemon | citrus | lemons |  |
| lime | Lime | citrus | limes |  |
| musaceae | Musaceae | fruit-trees | musa | our grouping |
| banana | Banana | musaceae | bananas, guineo |  |
| plantain | Plantain | musaceae | plantains |  |
| berries | Berries | fruit-trees | berry | group from a Silverstrike row |
| strawberry | Strawberry | berries | strawberries |  |
| raspberry | Raspberry | berries | raspberries |  |
| blackberry | Blackberry | berries | blackberries, bramble |  |
| blueberry | Blueberry | berries | blueberries |  |
| deciduous-fruit-trees | Deciduous fruit trees | fruit-trees | deciduous, temperate fruit trees | our grouping |
| peach | Peach | deciduous-fruit-trees | peaches |  |
| apple | Apple | deciduous-fruit-trees | apples, apple tree |  |
| pear | Pear | deciduous-fruit-trees | pears |  |
| plum | Plum | deciduous-fruit-trees | plums |  |
| grapevine | Grapevine | deciduous-fruit-trees | grape, grapes, vine |  |
| walnut | Walnut | deciduous-fruit-trees | walnuts, walnut tree |  |
| tropical-fruit-trees | Tropical fruit trees | fruit-trees | tropicals, tropical fruit | group from a Trico row |
| avocado | Avocado | tropical-fruit-trees | avocados |  |
| mango | Mango | tropical-fruit-trees | mangoes |  |
| papaya | Papaya | tropical-fruit-trees | papayas |  |
| pineapple | Pineapple | tropical-fruit-trees | pineapples |  |
| guava | Guava | tropical-fruit-trees | guavas |  |
| rambutan | Rambutan | tropical-fruit-trees |  |  |
| mangosteen | Mangosteen | tropical-fruit-trees |  |  |
| sapodilla | Sapodilla | tropical-fruit-trees | chicozapote |  |
| dragon-fruit | Dragon fruit | tropical-fruit-trees | pitahaya, pitaya |  |
| cacao | Cacao | tropical-fruit-trees | cocoa |  |
| macadamia | Macadamia | tropical-fruit-trees |  |  |
| grains | Grains |  | grain, staple grains, cereals, grasses | our grouping. Sugarcane is a grass and is not here: it is treated as industrial |
| corn | Corn | grains | maize, elote |  |
| sweet-corn | Sweet corn | grains |  |  |
| rice | Rice | grains |  |  |
| oats | Oats | grains | oat |  |
| ornamentals | Ornamentals |  | ornamental | one datasheet names it as if it were a crop |
| roses | Roses | ornamentals | rose, rose bush |  |
| carnation | Carnation | ornamentals | carnations |  |
| chrysanthemum | Chrysanthemum | ornamentals | chrysanthemums |  |
| gerbera | Gerbera | ornamentals |  |  |
| gladiolus | Gladiolus | ornamentals | gladiola, glandiola | glandiola is how one of the datasheets writes it |
| lisianthus | Lisianthus | ornamentals | lisanthus |  |
| zinnia | Zinnia | ornamentals |  |  |
| sunflower | Sunflower | ornamentals | sunflowers |  |
| leatherleaf-fern | Leatherleaf fern | ornamentals | leatherleaf |  |
| flowers | Flowers | ornamentals | flower |  |
| foliage | Foliage | ornamentals | foliage plants |  |
| industrial-crops | Industrial crops |  | industrial | our grouping |
| coffee | Coffee | industrial-crops |  |  |
| sugarcane | Sugarcane | industrial-crops | sugar cane | botanically it is a grass. It hangs from here because it is sold and treated as industrial |
| african-oil-palm | African oil palm | industrial-crops | palm, oil palm |  |
| cotton | Cotton | industrial-crops |  |  |
| cardamom | Cardamom | industrial-crops |  |  |
| black-pepper | Black pepper | industrial-crops |  |  |
| stevia | Stevia | industrial-crops |  |  |
| aloe-vera | Aloe vera | industrial-crops | aloe, savila |  |
| pastures | Pastures |  | pasture | sixth root. Vetvane is veterinary and its "use" is the pasture, not a harvested crop |
