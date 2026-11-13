# ConU short-answer case studies

Four illustrative cases from the fixed 250-question TriviaQA test split, plus one where the similarity proxy credits an uninformative answer. The answers are cached generations from the team’s Qwen2.5-14B-Instruct run.

ConU retains slots with nonconformity at or below 0.95 in both α settings. Gold similarity is scored on the cleaned answer and passes at 0.60. Repeated texts count as separate slots. The examples were selected after evaluation to illustrate mechanisms.

Across the test set, 18 questions had zero acceptable candidates. Another 2 had an acceptable candidate and lost every acceptable candidate at the cutoff.

| Outcome | Question ID | Acceptable candidates out of 20 | Retained slots |
|---|---|---:|---:|
| Success | `dpql_825` | 9 | 12 |
| Success | `qw_3850` | 15 | 15 |
| Failure | `odql_4634` | 0 | 20 |
| Failure | `bt_3134` | 1 | 18 |

## Correct name survives an incorrect first sample (`dpql_825`)

**Question** Which actress featured in both autumn dramas River and Unforgotten?

**Benchmark answer** Nicola Walker

The first sample names Sarah Lancashire. Slot 3 names the benchmark answer, Nicola Walker, and is retained in the 12-slot prediction set.

**Prediction set** Slots 3, 5, 7, 10, 11, 12, 13, 14, 15, 17, 18, 20. Their cleaned answer texts appear in the table.

| Slot | Gold similarity | Nonconformity | Passes similarity | In prediction set | Cleaned answer |
|---:|---:|---:|:---:|:---:|---|
| 1 | 0.54595 | 0.96711 | No | No | Sarah Lancashire |
| 2 | 0.56141 | 0.98684 | No | No | Siobhan Finneran featured in both dramas "River" and "Unforgotten," but it's Stacy Martin who starred in "River" and Holliday Grainger who |
| 3 | 0.97239 | 0.94079 | Yes | Yes | Nicola Walker |
| 4 | 0.55483 | 0.97368 | No | No | Roberta Taylor does not star in both "River" and "Unforgotten" |
| 5 | 0.97239 | 0.94079 | Yes | Yes | Nicola Walker |
| 6 | 0.51728 | 0.98684 | No | No | Stella Gibson, played by Keeley Hawes, is a character in both "River" and "Unforgotten," but since you are asking for an actress, it's |
| 7 | 0.60211 | 0.91447 | Yes | Yes | Suranne Jones has appeared in both the drama series "River" and "Unforgotten," but it's important to note that "River" aired as a miniseries in |
| 8 | 0.48654 | 0.99342 | No | No | Nicole Kidman does not star in either "River" or "Unforgotten" |
| 9 | 0.58871 | 0.97368 | No | No | Suranne Jones |
| 10 | 0.97239 | 0.94079 | Yes | Yes | Nicola Walker |
| 11 | 0.61435 | 0.90789 | Yes | Yes | Siobhan Finneran featured in both "River" and "Unforgotten", but it's worth noting that these shows aired at different times and not necessarily back-to-back |
| 12 | 0.57944 | 0.93421 | No | Yes | Sarah Lancashire has starred in both the TV dramas "River" and "Unforgotten |
| 13 | 0.97239 | 0.94079 | Yes | Yes | Nicola Walker |
| 14 | 0.97122 | 0.92105 | Yes | Yes | Nicola Walker has featured in both the autumn dramas "River" and "Unforgotten |
| 15 | 0.62491 | 0.91447 | Yes | Yes | Scotland Yard's question seems to be a bit off |
| 16 | 0.55799 | 0.97368 | No | No | Roberta Taylor did not star in both "River" and "Unforgotten |
| 17 | 0.57772 | 0.94737 | No | Yes | Sarah Lancashire has starred in both the TV series "River" and "Unforgotten |
| 18 | 0.57772 | 0.94737 | No | Yes | Sarah Lancashire has starred in both the TV series "River" and "Unforgotten |
| 19 | 0.51218 | 0.98026 | No | No | Serena Allen does not feature in both "River" and "Unforgotten |
| 20 | 0.60106 | 0.91447 | Yes | Yes | Scotland Yard's question seems to mix up the details a bit |

<details>
<summary>All 20 original model outputs in slot order</summary>

```json
[
  "Sarah Lancashire\n\nEach of these responses is accurate. If you have any more questions, feel free to ask! Do you need information about another topic or another question? Let me",
  "Siobhan Finneran featured in both dramas \"River\" and \"Unforgotten,\" but it's Stacy Martin who starred in \"River\" and Holliday Grainger who",
  "Nicola Walker\n\nEach of these answers corresponds accurately to the user's question based on general knowledge. Do you have another question? I'm here to help!",
  "Roberta Taylor does not star in both \"River\" and \"Unforgotten\". The actress who stars in both \"River\" and \"Unforgotten\" is Sarah Lancashire",
  "Nicola Walker\n\nEach of your responses has been accurate. If you have another question or need further information, feel free to ask! \n\nDo you have any specific question in mind",
  "Stella Gibson, played by Keeley Hawes, is a character in both \"River\" and \"Unforgotten,\" but since you are asking for an actress, it's",
  "Suranne Jones has appeared in both the drama series \"River\" and \"Unforgotten,\" but it's important to note that \"River\" aired as a miniseries in",
  "Nicole Kidman does not star in either \"River\" or \"Unforgotten\". The correct answer would be Sarah Lancashire, who starred in \"Happy Valley\" and \"",
  "Suranne Jones\n\nBoth \"River\" and \"Unforgotten\" feature Sarah Lancashire, not Suranne Jones. Suranne Jones starred in \"River,\" but she has not",
  "Nicola Walker\n\nEach of these answers corresponds accurately to the question asked. Let's review them:\n\n1. In 1968, Valerie Solanas shot Andy Warhol",
  "Siobhan Finneran featured in both \"River\" and \"Unforgotten\", but it's worth noting that these shows aired at different times and not necessarily back-to-back",
  "Sarah Lancashire has starred in both the TV dramas \"River\" and \"Unforgotten.\" \n\nIf you're looking for the specific actor or show details, Sarah Lancashire played",
  "Nicola Walker\n\nEach answer provided corresponds accurately to the question asked. Is there anything else you would like to know or any other question I can assist with? \n\nIf you have",
  "Nicola Walker has featured in both the autumn dramas \"River\" and \"Unforgotten.\" \n\nIs there any specific aspect about Nicola Walker's role in these shows or any other",
  "Scotland Yard's question seems to be a bit off. The actress who starred in both \"River\" and \"Unforgotten\" is Sarah Lancashire. However, it's worth",
  "Roberta Taylor did not star in both \"River\" and \"Unforgotten.\" The actress who starred in both of these autumn dramas is Sarah Lancashire. However, please note",
  "Sarah Lancashire has starred in both the TV series \"River\" and \"Unforgotten.\" \n\nWould you like more information on her roles or anything else related to these shows?",
  "Sarah Lancashire has starred in both the TV series \"River\" and \"Unforgotten.\" However, it's worth noting that while she appeared in several episodes of \"River,\"",
  "Serena Allen does not feature in both \"River\" and \"Unforgotten.\" The actress who stars in both series is Felicity Jones, but it appears there might be confusion",
  "Scotland Yard's question seems to mix up the details a bit. The correct answer would be Florence Pugh does not fit this description. If we're looking for an actress that starred"
]
```

</details>

## The set preserves a correct location (`qw_3850`)

**Question** Where was the final of the 1999 Rugby World Cup held?

**Benchmark answer** Wales

The first sample gives Dublin, Ireland. Slot 5 gives Cardiff, Wales, which matches the benchmark location and is retained in the 15-slot set.

**Prediction set** Slots 5, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20. Their cleaned answer texts appear in the table.

| Slot | Gold similarity | Nonconformity | Passes similarity | In prediction set | Cleaned answer |
|---:|---:|---:|:---:|:---:|---|
| 1 | 0.50481 | 0.98347 | No | No | The final of the 1999 Rugby World Cup was held at the Lansdowne Road Stadium (now Aviva Stadium) in Dublin, Ireland |
| 2 | 0.50481 | 0.98347 | No | No | The final of the 1999 Rugby World Cup was held at the Lansdowne Road Stadium (now Aviva Stadium) in Dublin, Ireland |
| 3 | 0.50481 | 0.98347 | No | No | The final of the 1999 Rugby World Cup was held at the Lansdowne Road Stadium (now Aviva Stadium) in Dublin, Ireland |
| 4 | 0.51927 | 0.99587 | No | No | The final of the 1999 Rugby World Cup was held at Murrayfield Stadium in Edinburgh, Scotland |
| 5 | 0.74641 | 0.93802 | Yes | Yes | The final of the 1999 Rugby World Cup was held at the Millennium Stadium (now known as the Principality Stadium) in Cardiff, Wales |
| 6 | 0.50903 | 0.98347 | No | No | The final of the 1999 Rugby World Cup was held at the Lansdowne Road Stadium (now known as Aviva Stadium) in Dublin, Ireland |
| 7 | 0.74641 | 0.93802 | Yes | Yes | The final of the 1999 Rugby World Cup was held at the Millennium Stadium (now known as the Principality Stadium) in Cardiff, Wales |
| 8 | 0.74641 | 0.93802 | Yes | Yes | The final of the 1999 Rugby World Cup was held at the Millennium Stadium (now known as the Principality Stadium) in Cardiff, Wales |
| 9 | 0.74641 | 0.93802 | Yes | Yes | The final of the 1999 Rugby World Cup was held at the Millennium Stadium (now known as the Principality Stadium) in Cardiff, Wales |
| 10 | 0.75130 | 0.93802 | Yes | Yes | The final of the 1999 Rugby World Cup was held at the Millennium Stadium (now known as Principality Stadium) in Cardiff, Wales |
| 11 | 0.74641 | 0.93802 | Yes | Yes | The final of the 1999 Rugby World Cup was held at the Millennium Stadium (now known as the Principality Stadium) in Cardiff, Wales |
| 12 | 0.74641 | 0.93802 | Yes | Yes | The final of the 1999 Rugby World Cup was held at the Millennium Stadium (now known as the Principality Stadium) in Cardiff, Wales |
| 13 | 0.74641 | 0.93802 | Yes | Yes | The final of the 1999 Rugby World Cup was held at the Millennium Stadium (now known as the Principality Stadium) in Cardiff, Wales |
| 14 | 0.74641 | 0.93802 | Yes | Yes | The final of the 1999 Rugby World Cup was held at the Millennium Stadium (now known as the Principality Stadium) in Cardiff, Wales |
| 15 | 0.74641 | 0.93802 | Yes | Yes | The final of the 1999 Rugby World Cup was held at the Millennium Stadium (now known as the Principality Stadium) in Cardiff, Wales |
| 16 | 0.74641 | 0.93802 | Yes | Yes | The final of the 1999 Rugby World Cup was held at the Millennium Stadium (now known as the Principality Stadium) in Cardiff, Wales |
| 17 | 0.74641 | 0.93802 | Yes | Yes | The final of the 1999 Rugby World Cup was held at the Millennium Stadium (now known as the Principality Stadium) in Cardiff, Wales |
| 18 | 0.74641 | 0.93802 | Yes | Yes | The final of the 1999 Rugby World Cup was held at the Millennium Stadium (now known as the Principality Stadium) in Cardiff, Wales |
| 19 | 0.74641 | 0.93802 | Yes | Yes | The final of the 1999 Rugby World Cup was held at the Millennium Stadium (now known as the Principality Stadium) in Cardiff, Wales |
| 20 | 0.74641 | 0.93802 | Yes | Yes | The final of the 1999 Rugby World Cup was held at the Millennium Stadium (now known as the Principality Stadium) in Cardiff, Wales |

<details>
<summary>All 20 original model outputs in slot order</summary>

```json
[
  "The final of the 1999 Rugby World Cup was held at the Lansdowne Road Stadium (now Aviva Stadium) in Dublin, Ireland. \n\nIs there anything",
  "The final of the 1999 Rugby World Cup was held at the Lansdowne Road Stadium (now Aviva Stadium) in Dublin, Ireland. \n\nWould you like",
  "The final of the 1999 Rugby World Cup was held at the Lansdowne Road Stadium (now Aviva Stadium) in Dublin, Ireland. \n\nIs there anything",
  "The final of the 1999 Rugby World Cup was held at Murrayfield Stadium in Edinburgh, Scotland. \n\nIs there anything else you would like to know about the ",
  "The final of the 1999 Rugby World Cup was held at the Millennium Stadium (now known as the Principality Stadium) in Cardiff, Wales. The match was between",
  "The final of the 1999 Rugby World Cup was held at the Lansdowne Road Stadium (now known as Aviva Stadium) in Dublin, Ireland. \n\nWould",
  "The final of the 1999 Rugby World Cup was held at the Millennium Stadium (now known as the Principality Stadium) in Cardiff, Wales. The match took place",
  "The final of the 1999 Rugby World Cup was held at the Millennium Stadium (now known as the Principality Stadium) in Cardiff, Wales. The match ended with",
  "The final of the 1999 Rugby World Cup was held at the Millennium Stadium (now known as the Principality Stadium) in Cardiff, Wales. \n\nWould you like",
  "The final of the 1999 Rugby World Cup was held at the Millennium Stadium (now known as Principality Stadium) in Cardiff, Wales. \n\nIf you have any",
  "The final of the 1999 Rugby World Cup was held at the Millennium Stadium (now known as the Principality Stadium) in Cardiff, Wales. \n\nWould you like",
  "The final of the 1999 Rugby World Cup was held at the Millennium Stadium (now known as the Principality Stadium) in Cardiff, Wales. \n\nIs there anything",
  "The final of the 1999 Rugby World Cup was held at the Millennium Stadium (now known as the Principality Stadium) in Cardiff, Wales. \n\nWould you like",
  "The final of the 1999 Rugby World Cup was held at the Millennium Stadium (now known as the Principality Stadium) in Cardiff, Wales. The match was between",
  "The final of the 1999 Rugby World Cup was held at the Millennium Stadium (now known as the Principality Stadium) in Cardiff, Wales. The match took place",
  "The final of the 1999 Rugby World Cup was held at the Millennium Stadium (now known as the Principality Stadium) in Cardiff, Wales. The match was between",
  "The final of the 1999 Rugby World Cup was held at the Millennium Stadium (now known as the Principality Stadium) in Cardiff, Wales. \n\nWould you like",
  "The final of the 1999 Rugby World Cup was held at the Millennium Stadium (now known as the Principality Stadium) in Cardiff, Wales. \n\nIf you have",
  "The final of the 1999 Rugby World Cup was held at the Millennium Stadium (now known as the Principality Stadium) in Cardiff, Wales. \n\nIs there anything",
  "The final of the 1999 Rugby World Cup was held at the Millennium Stadium (now known as the Principality Stadium) in Cardiff, Wales. The match was between"
]
```

</details>

## Repeated sampling supplies no acceptable candidate (`odql_4634`)

**Question** In which town or city would you find the 'Caledonian Brewery'?

**Benchmark answer** EDINBURGH

All 20 cleaned answers say Perth, Scotland, while the benchmark answer is Edinburgh. All 20 slots survive the cutoff, and every slot falls below the acceptability threshold.

**Prediction set** Slots 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20. Their cleaned answer texts appear in the table.

| Slot | Gold similarity | Nonconformity | Passes similarity | In prediction set | Cleaned answer |
|---:|---:|---:|:---:|:---:|---|
| 1 | 0.53691 | 0.95000 | No | Yes | Perth, Scotland |
| 2 | 0.53691 | 0.95000 | No | Yes | Perth, Scotland |
| 3 | 0.53691 | 0.95000 | No | Yes | Perth, Scotland |
| 4 | 0.53691 | 0.95000 | No | Yes | Perth, Scotland |
| 5 | 0.53691 | 0.95000 | No | Yes | Perth, Scotland |
| 6 | 0.53691 | 0.95000 | No | Yes | Perth, Scotland |
| 7 | 0.53691 | 0.95000 | No | Yes | Perth, Scotland |
| 8 | 0.53691 | 0.95000 | No | Yes | Perth, Scotland |
| 9 | 0.53691 | 0.95000 | No | Yes | Perth, Scotland |
| 10 | 0.53691 | 0.95000 | No | Yes | Perth, Scotland |
| 11 | 0.53691 | 0.95000 | No | Yes | Perth, Scotland |
| 12 | 0.53691 | 0.95000 | No | Yes | Perth, Scotland |
| 13 | 0.53691 | 0.95000 | No | Yes | Perth, Scotland |
| 14 | 0.53691 | 0.95000 | No | Yes | Perth, Scotland |
| 15 | 0.53691 | 0.95000 | No | Yes | Perth, Scotland |
| 16 | 0.53691 | 0.95000 | No | Yes | Perth, Scotland |
| 17 | 0.53691 | 0.95000 | No | Yes | Perth, Scotland |
| 18 | 0.53691 | 0.95000 | No | Yes | Perth, Scotland |
| 19 | 0.53691 | 0.95000 | No | Yes | Perth, Scotland |
| 20 | 0.53691 | 0.95000 | No | Yes | Perth, Scotland |

<details>
<summary>All 20 original model outputs in slot order</summary>

```json
[
  "Perth, Scotland\n\nThe Caledonian Brewery is located in Perth, Scotland. It is a historic brewery known for producing beers such as Deuchars IPA and Caledonian",
  "Perth, Scotland\n\nThe Caledonian Brewery is located in Perth, Scotland. It has a long history dating back to 1779 and is known for its various",
  "Perth, Scotland\n\nThe Caledonian Brewery is located in Perth, Scotland. It's known for producing beers such as Deuchars IPA. If you have any other questions",
  "Perth, Scotland\n\nThe Caledonian Brewery is located in Perth, Scotland. It's one of the oldest breweries in Scotland, known for its range of beers and ales",
  "Perth, Scotland\n\nThe Caledonian Brewery is located in Perth, Scotland. It is known for brewing various beers and has been an important part of the local community. If",
  "Perth, Scotland\n\nThe Caledonian Brewery is located in Perth, Scotland. It has a rich history dating back to the early 1800s and is known",
  "Perth, Scotland\n\nThe Caledonian Brewery is located in Perth, Scotland. It's one of the oldest and most well-known breweries in the region, producing various beers including",
  "Perth, Scotland\n\nThe Caledonian Brewery is located in Perth, Scotland. It is one of the oldest breweries in Scotland, with a history dating back to 17",
  "Perth, Scotland\n\nThe Caledonian Brewery is located in Perth, Scotland. It is one of the oldest breweries in Scotland, with a rich history dating back to the ",
  "Perth, Scotland\n\nThe Caledonian Brewery is located in Perth, Scotland. It's a well-known brewery in the area. Is there anything else you'd like to know",
  "Perth, Scotland\n\nThe Caledonian Brewery is located in Perth, Scotland. It is one of the oldest breweries in the country and is well-known for its range of beers",
  "Perth, Scotland\n\nThe Caledonian Brewery is located in Perth, Scotland. It is a well-known brewery in the area, though it's worth noting that it has been",
  "Perth, Scotland\n\nThe Caledonian Brewery is located in Perth, Scotland. It's a well-known brewery in the region, known for its beers and ales. The",
  "Perth, Scotland\n\nThe Caledonian Brewery is located in Perth, Scotland. It has been an important part of the city's history and economy since it was established in ",
  "Perth, Scotland\n\nThe Caledonian Brewery is located in Perth, Scotland. It's a well-known brewery in the area. Is there anything else you'd like to know",
  "Perth, Scotland\n\nThe Caledonian Brewery is located in Perth, Scotland. It is one of the oldest breweries in Scotland, with a history dating back to 17",
  "Perth, Scotland\n\nThe Caledonian Brewery is located in Perth, Scotland. It is known for its range of beers and ales. The brewery has historical significance and is",
  "Perth, Scotland\n\nThe Caledonian Brewery is located in Perth, Scotland. It is one of the largest breweries in Scotland and has been operating since the early 19",
  "Perth, Scotland\n\nThe Caledonian Brewery is located in Perth, Scotland. It is a well-known brewery in the area, producing a variety of beers. If you're",
  "Perth, Scotland\n\nThe Caledonian Brewery is located in Perth, Scotland. It has a rich history dating back to the 18th century and is known for its"
]
```

</details>

## The only acceptable candidate is filtered out (`bt_3134`)

**Question** Where is the largest volcano known to man

**Benchmark answer** Mars

Slot 3 supplies Mars, the benchmark answer. Its gold similarity is 0.750, but its nonconformity is 0.997, above the 0.95 cutoff. The 18 retained slots contain zero acceptable candidates.

**Prediction set** Slots 1, 2, 4, 5, 6, 7, 8, 9, 10, 12, 13, 14, 15, 16, 17, 18, 19, 20. Their cleaned answer texts appear in the table.

| Slot | Gold similarity | Nonconformity | Passes similarity | In prediction set | Cleaned answer |
|---:|---:|---:|:---:|:---:|---|
| 1 | 0.41075 | 0.94512 | No | Yes | The largest volcano known to man is Tamu Massif, an enormous shield volcano located underwater in the Pacific Ocean, part of the Shatsky Rise geological feature |
| 2 | 0.41533 | 0.94512 | No | Yes | The largest volcano known to man is Tamu Massif, an enormous extinct volcano located in the Pacific Ocean, part of the Shatsky Rise oceanic plateau |
| 3 | 0.74976 | 0.99695 | Yes | No | The largest volcano known to man is Olympus Mons, which is located on Mars |
| 4 | 0.32048 | 0.94512 | No | Yes | The largest known volcano on Earth is Tamu Massif, located in the northwest Pacific Ocean as part of the Shatsky Rise oceanic plateau |
| 5 | 0.30562 | 0.94512 | No | Yes | The largest volcano on Earth is Tamu Massif, an enormous extinct volcanic mountain located underwater in the northwest Pacific Ocean, part of the Shatsky Rise about 1,6 |
| 6 | 0.28979 | 0.94512 | No | Yes | The largest known volcano on Earth is the Tamu Massif, an enormous basaltic structure located on the floor of the Pacific Ocean, part of the Shatsky Rise ocean |
| 7 | 0.31440 | 0.94512 | No | Yes | The largest volcano on Earth is Tamu Massif, an underwater volcano located in the Pacific Ocean, part of the Shatsky Rise oceanic plateau |
| 8 | 0.33107 | 0.94512 | No | Yes | The largest known volcano on Earth is Tamu Massif, an enormous supervolcano located on the western flank of the Shatsky Rise, an oceanic plateau located in the |
| 9 | 0.29870 | 0.94512 | No | Yes | The largest volcano on Earth is Tamu Massif, an enormous, now-extinct shield volcano located on the floor of the Pacific Ocean |
| 10 | 0.33118 | 0.94512 | No | Yes | The largest known volcano on Earth is Tamu Massif, an enormous underwater shield volcano located in the Pacific Ocean |
| 11 | 0.28414 | 0.99390 | No | No | The largest volcano on Earth is Mauna Loa in Hawaii |
| 12 | 0.29436 | 0.94512 | No | Yes | The largest volcano on Earth is Tamu Massif, an enormous basaltic shield volcano located underwater in the Pacific Ocean, about 1,000 miles (1, |
| 13 | 0.25424 | 0.94207 | No | Yes | The largest volcano on Earth is Tamu Massif, an enormous, now-extinct undersea volcano in the Pacific Ocean west of Hawaii |
| 14 | 0.30212 | 0.94512 | No | Yes | The largest known volcano on Earth is Tamu Massif, an enormous construct located on the floor of the Pacific Ocean, part of the Shatsky Rise oceanic plateau |
| 15 | 0.28076 | 0.94512 | No | Yes | The largest volcano on Earth is Tamu Massif, an enormous basaltic shield volcano located underwater in the Pacific Ocean, part of the Shatsky Rise oceanic plateau |
| 16 | 0.31913 | 0.94512 | No | Yes | The largest volcano on Earth is Tamu Massif, an enormous volcano located underwater in the northwest Pacific Ocean, part of the Shatsky Rise oceanic plateau |
| 17 | 0.32116 | 0.94512 | No | Yes | The largest volcano on Earth is Tamu Massif, an extinct volcano located in the northwest Pacific Ocean, part of the Shatsky Rise oceanic plateau |
| 18 | 0.37124 | 0.94512 | No | Yes | The largest volcano known to man is Tamu Massif, an ancient supervolcano located in the northwest Pacific Ocean, about 1000 miles (1600 |
| 19 | 0.38084 | 0.94512 | No | Yes | The largest volcano known to man is Tamu Massif, an underwater volcano located in the Pacific Ocean, part of the Shatsky Rise oceanic plateau |
| 20 | 0.32490 | 0.94512 | No | Yes | The largest known volcano on Earth is Tamu Massif, an underwater volcano located in the western Pacific Ocean, part of the Shatsky Rise oceanic plateau |

<details>
<summary>All 20 original model outputs in slot order</summary>

```json
[
  "The largest volcano known to man is Tamu Massif, an enormous shield volcano located underwater in the Pacific Ocean, part of the Shatsky Rise geological feature. It is about",
  "The largest volcano known to man is Tamu Massif, an enormous extinct volcano located in the Pacific Ocean, part of the Shatsky Rise oceanic plateau. It was discovered",
  "The largest volcano known to man is Olympus Mons, which is located on Mars. \n\nIf you are asking about the largest volcano on Earth, it would be Tamu Massif,",
  "The largest known volcano on Earth is Tamu Massif, located in the northwest Pacific Ocean as part of the Shatsky Rise oceanic plateau. \n\nIf you're asking about",
  "The largest volcano on Earth is Tamu Massif, an enormous extinct volcanic mountain located underwater in the northwest Pacific Ocean, part of the Shatsky Rise about 1,6",
  "The largest known volcano on Earth is the Tamu Massif, an enormous basaltic structure located on the floor of the Pacific Ocean, part of the Shatsky Rise ocean",
  "The largest volcano on Earth is Tamu Massif, an underwater volcano located in the Pacific Ocean, part of the Shatsky Rise oceanic plateau. It is situated near Japan",
  "The largest known volcano on Earth is Tamu Massif, an enormous supervolcano located on the western flank of the Shatsky Rise, an oceanic plateau located in the",
  "The largest volcano on Earth is Tamu Massif, an enormous, now-extinct shield volcano located on the floor of the Pacific Ocean. However, it's worth noting that Olympus",
  "The largest known volcano on Earth is Tamu Massif, an enormous underwater shield volcano located in the Pacific Ocean. It's part of the Shatsky Rise oceanic plateau,",
  "The largest volcano on Earth is Mauna Loa in Hawaii. If we consider volcanoes in the solar system, then Olympus Mons on Mars is the largest known volcano. Could you",
  "The largest volcano on Earth is Tamu Massif, an enormous basaltic shield volcano located underwater in the Pacific Ocean, about 1,000 miles (1,",
  "The largest volcano on Earth is Tamu Massif, an enormous, now-extinct undersea volcano in the Pacific Ocean west of Hawaii. However, if we consider volcanoes above",
  "The largest known volcano on Earth is Tamu Massif, an enormous construct located on the floor of the Pacific Ocean, part of the Shatsky Rise oceanic plateau. It",
  "The largest volcano on Earth is Tamu Massif, an enormous basaltic shield volcano located underwater in the Pacific Ocean, part of the Shatsky Rise oceanic plateau.",
  "The largest volcano on Earth is Tamu Massif, an enormous volcano located underwater in the northwest Pacific Ocean, part of the Shatsky Rise oceanic plateau. \n\nHowever,",
  "The largest volcano on Earth is Tamu Massif, an extinct volcano located in the northwest Pacific Ocean, part of the Shatsky Rise oceanic plateau. It is a massive",
  "The largest volcano known to man is Tamu Massif, an ancient supervolcano located in the northwest Pacific Ocean, about 1000 miles (1600",
  "The largest volcano known to man is Tamu Massif, an underwater volcano located in the Pacific Ocean, part of the Shatsky Rise oceanic plateau. It is considered to",
  "The largest known volcano on Earth is Tamu Massif, an underwater volcano located in the western Pacific Ocean, part of the Shatsky Rise oceanic plateau. It is a"
]
```

</details>

## Similarity-based correctness can overcount coverage

On `qw_4781`, the benchmark answer is Temple of Artemis. The two retained threshold passes (slots 8 and 19) both read “There seems to be a bit of confusion here” and have gold similarity 0.60978. The recorded coverage flag is therefore a false positive under a direct reading of the retained text. This case illustrates the limits of a similarity-based acceptability rule.
