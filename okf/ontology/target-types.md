---
type: ontology
schema: wiki/ontology/v1
axis: target-types
label: "Target types"
generated: { by: claude-code/claude-opus-5, at: 2026-08-27T07:05:54Z }
---

What class of thing the product controls. It is the `kind` of each target in the agronomic profile,
and it serves where the common name falls short: a customer who asks "do you have anything for
fungus?" does not know whether theirs is anthracnose or mildew.

There are six because the datasheets name six. There are no weeds or bacterial targets in this
catalog: no product claims herbicidal or bactericidal action, and the two times the word herbicide
appears it is to say what not to mix with.

`deficiency` is not a pest and gets in anyway. Half the catalog is nutrition, and what an iron foliar
corrects is a shortage, not an organism.

| id | label | parent | alias | note |
|---|---|---|---|---|
| insect | Insect |  | insects |  |
| mite | Mite |  | mites |  |
| nematode | Nematode |  | nematodes |  |
| fungus | Fungus |  | fungi | includes oomycetes such as Pythium and Phytophthora. The datasheets do not separate them and neither does the customer |
| rodent | Rodent |  | rodents |  |
| deficiency | Nutrient deficiency |  | shortage, nutrient deficiency |  |
