# B · Conformal Factuality 案例分析

## 1. 分析结论

本节分析使用主设置：

- \(1-\alpha=0.9\)
- calibration 使用完整 20 条 pool
- 固定 test 为 25 条
- calibrated threshold：`4.9996421406662925`
- 正确标注：`Y`、`S`
- 错误标注：`N`、`U`

主要结论：

1. Claim filtering 能明显提高 retained claims 的正确性，但它优化的是“留下来的内容是否可靠”，不是“回答是否完整”。
2. 7 / 25 条 test 回答被完全删空；空响应满足“没有错误 claim”，但对用户没有信息价值。
3. 17 / 25 条 test 回答非空且所有 retained claims 都正确。
4. 1 / 25 条回答在过滤后仍保留错误 claim，说明频率分数并不保证一定选对。
5. 正确的高分 claim 可能被保留，错误的低分 claim 会被删除；但正确的低频 claim 也可能被误删。

25 条 test 的互斥结果统计：

| 结果 | 数量 |
|---|---:|
| 非空且 retained claims 全对 | 17 |
| 空响应 | 7 |
| 非空但 retained claims 中仍有错误 | 1 |
| 合计 | 25 |

## 2. 数据限制

上游 `factscore_annotations.jsonl` 不保存原始回答。只有
`out/factscore_survey.json` 保存了最后 30 个 prompt 的原始回答与上游过滤结果。

因此：

- 25 条 test 中有 14 条能恢复原始回答。
- 本文所有原始回答案例都从这 14 条中选择。
- 另外 11 条 test 只能计算 claim 保留结果，不能展示完整原回答。
- 本文没有重新调用模型合并 claims；所谓“过滤后的回答”指 retained claims
  所包含的信息，不假装生成新的流畅段落。

## 3. 缓存中的样本排除审计

从上游缓存可以直接观察到：

| 项目 | 数量 | 说明 |
|---|---:|---|
| 总 response | 50 | 全部 prompt 都有 claim 记录 |
| claim 数为 0 的 response | 0 | 没有观察到整条回答拆不出 claim |
| 上游 merged response | 50 | 50 条都有 merged 输出记录 |
| 缺少 merged response | 0 | 没有整条记录缺失 |
| 缺少 `accepted-subclaims` 字段 | 0 | 没有 merge 结果字段缺失 |
| `accepted-subclaims` 为空 | 4 | 过滤后没有 claim |
| 缺少 `new-output` | 0 | 没有字段缺失 |
| `new-output` 为空字符串 | 0 | 空 claim 会生成 `Abstain.` |
| `new-output == "Abstain."` | 4 | 与 `accepted-subclaims=0` 完全对应 |

这里的 4 条 empty 来自上游 cache 的 `a=1, alpha=0.2` 结果，不是本文主实验
`alpha=0.1` 的 7 条 empty，不能用两组数字互相替代。

结论：

- 已发布的 cache 没有在 response 层面静默删除困难样本。
- Claim 拆分或 merge 解析失败率无法得知，因为上游没有保存失败日志；该比例必须
  写成 `unknown`，不能写成 0。

## 4. 成功案例

### 4.1 Sharad Kumar：删除错误奖牌，保留完整人物主线

- ID：`factscore-0027`
- Prompt：`Sharad Kumar (athlete)`
- 原始 claims：13
- 错误 claims：5
- 保留 claims：4
- 错误 claims 保留数：0
- Retention：\(4/13=30.8\%\)
- 判断：**成功。** 虽然删除了不少次要信息，但保留了身份、项目、出生信息和一项
  重要成就，仍足以回答人物简介。

原始回答：

> Sharad Kumar is an Indian para-athlete who competes in high jump events. He was
> born on March 1, 1992, in Bihar, India. Kumar was diagnosed with polio at a
> young age, which affected his left leg. Despite this, he pursued his passion
> for sports and began training as a high jumper. Kumar has represented India in
> several international competitions and has won numerous medals. He won a gold
> medal at the 2014 Asian Para Games in Incheon, South Korea, and a silver medal
> at the 2018 Asian Para Games in Jakarta, Indonesia. He also won a bronze medal
> at the 2017 World Para Athletics Championships in London. In 2021, Kumar won a
> bronze medal in the men's high jump T42 category at the Tokyo Paralympics,
> marking his first Paralympic medal. His personal best in high jump is 1.90
> meters, which he achieved at the 2017 World Para Athletics Championships.

| # | Claim | 标注 | 分数 + noise | 决策 |
|---:|---|---:|---:|---|
| 0 | Sharad Kumar is an Indian para-athlete who competes in high jump events. | Y | 5.0012 | 保留 |
| 1 | Sharad Kumar was born on March 1, 1992, in Bihar, India. | Y | 5.0011 | 保留 |
| 2 | Sharad Kumar was diagnosed with polio at a young age, which affected his left leg. | U | 2.9993 | 删除 |
| 3 | Despite his condition, Sharad Kumar pursued his passion for sports and began training as a high jumper. | Y | 4.0004 | 删除 |
| 4 | Sharad Kumar has represented India in several international competitions. | Y | 5.0006 | 保留 |
| 5 | Sharad Kumar has won numerous medals in his career. | Y | 4.9994 | 删除 |
| 6 | Sharad Kumar won a gold medal at the 2014 Asian Para Games. | Y | 0.9997 | 删除 |
| 7 | Sharad Kumar won a silver medal at the 2018 Asian Para Games. | N | 0.0005 | 删除 |
| 8 | Sharad Kumar won a bronze medal at the 2017 World Para Athletics Championships. | N | -0.9968 | 删除 |
| 9 | Sharad Kumar won bronze in the men's high jump T42 at the Tokyo Paralympics. | Y | 5.0017 | 保留 |
| 10 | The Tokyo bronze was Sharad Kumar's first Paralympic medal. | Y | 1.9995 | 删除 |
| 11 | Sharad Kumar's personal best is 1.90 meters. | N | -1.0003 | 删除 |
| 12 | He achieved that personal best at the 2017 World Para Athletics Championships. | N | -0.9995 | 删除 |

分析：

- 两条错误奖牌 claim 被删除，主要幻觉得到抑制。
- 保留的身份、出生、参赛经历和 Tokyo medal 足以构成基本人物介绍。
- 代价是几条正确的次要信息也被删除，包括 polio 经历和 2014 gold medal。

### 4.2 Zamfir Arbore：过滤错误，但信息保留接近临界

- ID：`factscore-0049`
- Prompt：`Zamfir Arbore`
- 原始 claims：10
- 错误 claims：5
- 保留 claims：4
- 错误 claims 保留数：0
- Retention：\(4/10=40\%\)
- 判断：**部分成功。** 保留下来的内容正确且抓住身份、生卒年和地区，但删掉了
  historian、政治活动和流亡经历，人物介绍已明显变薄。

原始回答：

> Zamfir Ralli-Arbore (1848–1933) was a Romanian political activist and historian
> from Bessarabia, who spent much of his life in exile. As a member of the
> National Liberal Party, he campaigned for the union of his native region with
> the Kingdom of Romania, and was a prominent opponent of Russian and Soviet
> policies. He was also a noted historian, specializing in the history of
> Moldavia and Wallachia during the Middle Ages.

| # | Claim | 标注 | 分数 + noise | 决策 |
|---:|---|---:|---:|---|
| 0 | Zamfir Ralli-Arbore was born in 1848. | Y | 5.0012 | 保留 |
| 1 | Zamfir Ralli-Arbore died in 1933. | Y | 5.0003 | 保留 |
| 2 | Zamfir Ralli-Arbore was a Romanian political activist. | Y | 4.9999 | 保留 |
| 3 | Zamfir Ralli-Arbore was a historian. | Y | 2.9985 | 删除 |
| 4 | Zamfir Ralli-Arbore was from Bessarabia. | S | 4.9999 | 保留 |
| 5 | He spent much of his life in exile. | S | 1.0010 | 删除 |
| 6 | He was a member of the National Liberal Party. | N | -2.0005 | 删除 |
| 7 | He campaigned for union with the Kingdom of Romania. | U | 2.9996 | 删除 |
| 8 | He opposed Russian and Soviet policies. | Y | 0.9989 | 删除 |
| 9 | He specialized in medieval Moldavian and Wallachian history. | U | -0.0002 | 删除 |

分析：

- 五条错误或不可验证 claim 全部删除。
- “historian”其实正确，但 frequency score 只有约 3，被当作低置信信息删除。
- 这说明 filtering 的目标不是最大化信息量；它宁愿牺牲正确但低频的事实，也要
  降低保留错误内容的风险。

## 5. 事实正确但内容不足的案例

### 5.1 Rin Iwanaga：只剩“可能是普通人”

- ID：`factscore-0034`
- Prompt：`Rin Iwanaga`
- 原始 claims：5
- 错误 claims：1
- 保留 claims：1
- Retention：\(1/5=20\%\)
- 判断：**失败。** 保留下来的 claim 正确，但没有提供任何足以回答人物简介的事实。

原始回答：

> I'm sorry, but I couldn't find any information on a person named Rin Iwanaga.
> It's possible that you may have misspelled the name or the person you're asking
> about isn't widely known. If they're a private individual, it would be
> inappropriate to share personal details about them.

| # | Claim | 标注 | 分数 + noise | 决策 |
|---:|---|---:|---:|---|
| 0 | The assistant couldn't find information on a person named Rin Iwanaga. | Y | -1.0019 | 删除 |
| 1 | The name Rin Iwanaga might have been misspelled. | N | 2.9992 | 删除 |
| 2 | Rin Iwanaga isn't widely known. | S | 2.9984 | 删除 |
| 3 | Rin Iwanaga could be a private individual. | Y | 4.9998 | 保留 |
| 4 | It would be inappropriate to share details about a private individual. | S | 0.9999 | 删除 |

分析：

- 原回答本身主要是 abstention，没有实质人物信息。
- 过滤后只剩一个不确定性陈述“可能是私人个体”，因此 factuality 看似没问题，
  usefulness 几乎为零。
- 这是“正确但没有回答”的最直接例子。

### 5.2 Carlos Alfonso：只留下一个同名候选

- ID：`factscore-0046`
- Prompt：`Carlos Alfonso`
- 原始 claims：8
- 错误 claims：1
- 保留 claims：2
- Retention：\(2/8=25\%\)
- 判断：**部分失败。** 确实删除了错误内容，但也删掉了 baseball player 等其他解释，
  没有澄清用户问的是哪一位 Carlos Alfonso。

原始回答：

> There could be several individuals named Carlos Alfonso, as it is a common name
> in Spanish-speaking countries. Without more specific information, it's
> difficult to provide details. Some notable people named Carlos Alfonso include
> Carlos Alfonso (musician), a Cuban musician and member of the band Síntesis,
> and Carlos Alfonso (baseball), a former professional baseball player from the
> Dominican Republic. Please provide more details for more specific information.

| # | Claim | 标注 | 分数 + noise | 决策 |
|---:|---|---:|---:|---|
| 0 | There could be several individuals named Carlos Alfonso. | Y | 4.9998 | 保留 |
| 1 | Carlos Alfonso is a common name in Spanish-speaking countries. | S | 1.9982 | 删除 |
| 2 | Without more information, details are difficult to provide. | S | 4.9995 | 删除 |
| 3 | Notable people include Carlos Alfonso, a Cuban musician. | Y | 5.0011 | 保留 |
| 4 | The musician is a member of the band Síntesis. | Y | 3.0019 | 删除 |
| 5 | Another notable person is Carlos Alfonso, a former baseball player. | Y | -2.0002 | 删除 |
| 6 | The baseball player is from the Dominican Republic. | N | 0.0002 | 删除 |
| 7 | More details are needed for a specific answer. | S | 4.9991 | 删除 |

分析：

- 回答的核心问题其实是“名字有歧义”，过滤后仍保留了这个提示。
- 但它失去了第二种候选解释，用户无法理解为什么需要补充信息。
- 这说明 claim 层面的 correctness 无法保证消歧信息完整。

## 6. 完全删空的案例

### 6.1 Luis Guillermo Rivera

- ID：`factscore-0020`
- 原始 claims：10
- 正确 claims：1
- 保留 claims：0
- 判断：**过滤方向正确，但最终不可用。** 唯一可能正确的 claim 分数只有约 2，
  也低于阈值。

原始回答：

> Luis Guillermo Rivera is a professional athlete from Colombia who specializes
> in high jump. He was born on March 20, 1989 in Apartadó, Colombia. Rivera has
> represented Colombia in several international competitions, including the
> World Championships in Athletics and the Pan American Games. He won the gold
> medal in the high jump at the 2013 South American Championships in Athletics.
> His personal best in the high jump is 2.31 meters, which he achieved in 2013.

| # | Claim | 标注 | 分数 + noise | 决策 |
|---:|---|---:|---:|---|
| 0 | Luis Guillermo Rivera is a professional athlete from Colombia. | Y | 1.9990 | 删除 |
| 1 | Luis Guillermo Rivera specializes in high jump. | N | 2.0000 | 删除 |
| 2 | Luis Guillermo Rivera was born on March 20, 1989. | N | -0.0006 | 删除 |
| 3 | Luis Guillermo Rivera was born in Apartadó, Colombia. | N | 0.0011 | 删除 |
| 4 | Luis Guillermo Rivera has represented Colombia internationally. | N | 1.0013 | 删除 |
| 5 | Luis Guillermo Rivera competed at the World Championships. | N | 0.0005 | 删除 |
| 6 | Luis Guillermo Rivera competed at the Pan American Games. | N | -0.0002 | 删除 |
| 7 | Luis Guillermo Rivera won gold at the 2013 South American Championships. | N | -0.0014 | 删除 |
| 8 | Luis Guillermo Rivera's personal best is 2.31 meters. | N | -0.0013 | 删除 |
| 9 | Luis Guillermo Rivera achieved that personal best in 2013. | N | -0.0001 | 删除 |

分析：

- 原回答几乎整段错误，归零可以避免输出错误信息。
- 唯一正确 claim 因为 frequency score 低而未保留，说明 empty 不一定意味着原回答
  完全没有正确内容。
- 对用户而言，正确行为应是明确 abstain，而不是把空集合当成完成回答。

### 6.2 Roxana Díaz

- ID：`factscore-0023`
- 原始 claims：8
- 正确 claims：3
- 保留 claims：0
- 判断：**失败。** 三条正确 claim 全部被删除，最终没有提供任何信息。

原始回答：

> Roxana Díaz is a Venezuelan athlete who specializes in the 400 meters hurdles.
> She represented her country in various international competitions, including
> the World Championships and the Pan American Games. Díaz is known for her speed,
> agility, and determination on the track. She has won several medals throughout
> her career, making her one of the most successful athletes in her country.

| # | Claim | 标注 | 分数 + noise | 决策 |
|---:|---|---:|---:|---|
| 0 | Roxana Díaz is a Venezuelan athlete. | N | -0.9989 | 删除 |
| 1 | She specializes in the 400 meters hurdles. | N | -2.0011 | 删除 |
| 2 | Díaz has represented Venezuela in various international competitions. | N | 3.0002 | 删除 |
| 3 | She participated in the World Championships. | Y | 2.9999 | 删除 |
| 4 | She participated in the Pan American Games. | Y | 2.0008 | 删除 |
| 5 | Díaz is known for speed, agility, and determination. | S | 2.9994 | 删除 |
| 6 | She has won several medals. | N | 1.9996 | 删除 |
| 7 | She is one of the most successful athletes in Venezuela. | N | 0.9992 | 删除 |

分析：

- 保留的 World Championships 和 Pan American Games 信息是正确的，但 frequency
  分数约为 2 和 3，低于约 5 的阈值。
- 该案例说明频率分数可能把“正确但换个说法较少出现”的 claim 判低。
- 最终 empty 提高了 factuality 的表观安全性，却牺牲了全部可用信息。

## 7. 过滤失败的案例

### 7.1 Rennie Fritchie：高分错误 claim 被保留

- ID：`factscore-0047`
- 原始 claims：8
- 错误 claims：3
- 保留 claims：3
- 保留的错误 claims：1
- Retention：\(3/8=37.5\%\)
- 判断：**失败。** 最终 retained claims 并非全对。

原始回答：

> Rennie Fritchie, Baroness Fritchie, DBE (born 1942) is a British public servant
> and crossbench member of the House of Lords. She has held a number of
> high-profile roles in public service, including serving as the Commissioner for
> Public Appointments in the United Kingdom from 1999 to 2005. She was also the
> Chair of Nominet UK, the .uk domain name registry, from 2005 to 2010. In 2005,
> she was made a life peer as Baroness Fritchie, of Gloucester in the County of
> Gloucestershire. She has also served on the boards of several other
> organizations, including the BBC and the Prince's Trust.

| # | Claim | 标注 | 分数 + noise | 决策 |
|---:|---|---:|---:|---|
| 0 | Rennie Fritchie was born in 1942. | Y | 3.9997 | 删除 |
| 1 | Rennie Fritchie is a British public servant. | N | 5.0019 | 保留 |
| 2 | Rennie Fritchie is a crossbench member of the House of Lords. | Y | 5.0011 | 保留 |
| 3 | She held several high-profile public-service roles. | Y | 4.9987 | 删除 |
| 4 | She was Commissioner for Public Appointments from 1999 to 2005. | Y | 4.9994 | 删除 |
| 5 | She chaired Nominet UK from 2005 to 2010. | N | 0.0008 | 删除 |
| 6 | She became Baroness Fritchie, of Gloucester, in 2005. | Y | 5.0015 | 保留 |
| 7 | She served on BBC and Prince's Trust boards. | N | 0.0008 | 删除 |

分析：

- Claim 1 的高频分数约 5，因此通过了阈值，但缓存标注为 `N`。
- 这句话从常识看似乎合理，与 `N` 标注存在张力；它可能是 annotation noise，
  也可能是 FActScore 按特定规则判错。报告时应保留这一不确定性。
- 该案例说明基于 frequency 的 filtering 不能保证所有 retained claims 正确，
  尤其是错误内容被多个采样回答重复时。

## 8. 对 Part 2 问题的回答

### 8.1 为什么长回答需要 claim filtering

长回答通常同时包含正确和错误 statement。Sharad Kumar 和 Zamfir Arbore 案例显示，
过滤可以删除错误奖牌、党派或身份 claim，使保留内容更可靠。

### 8.2 过滤是否会让回答正确但不完整

会。最直接的是 7 条空响应。Rin Iwanaga 和 Carlos Alfonso 还展示了非空但不完整的
情况：留下内容正确，却不足以提供人物简介或解释名字歧义。

### 8.3 如果重复采样一直得不到正确答案

本实验使用仓库缓存好的 frequency score，没有重新执行 5 次采样，因此不能在当前
数据上精确复现“五次都没有正确回答”的过程。Luis Guillermo Rivera 和 Roxana Díaz
的低分正确 claim 说明，即使存在正确内容，只要其跨回答支持不足，也可能被全部删除。
更直接的采样失败分析需要后续保存原采样输出。

### 8.4 Coverage 与 factuality 为什么不能互换

- ConU 的 coverage 问：答案集合是否至少包含一个正确答案。
- Factuality 问：一段回答中保留下来的 claims 是否都正确。

一个空回答没有错误 claim，但也没有回答；一个包含 3 个答案的集合可能覆盖正确答案，
同时也包含错误答案。两者衡量的是不同对象，不能直接比较数值大小。

## 9. 审阅时建议重点判断

1. Zamfir Arbore 是否算“成功”还是“信息不足”，是本报告最依赖人工判断的边界案例。
2. Rin Iwanaga 和 Carlos Alfonso 的“不足以回答”判断是否合理。
3. Rennie Fritchie 的 `N` 标注是否可信；如果不信，应把它归为 annotation-quality
   case，而不是单纯 filtering failure。
4. 当前只分析 claim 保留情况，没有重新生成流畅 answer。报告中应明确这一点。

## 10. 复现

```bash
PYTHONPATH=src .venv/bin/python -m confqa.factuality.cli cases \
    --config configs/factuality.yaml
```

该命令输出主设置阈值、25 条 test 的三类结果计数和缓存排除审计。
