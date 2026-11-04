# B · Conformal Factuality 案例分析

## 1. 分析结论

本节分析使用主设置：

- \(1-\alpha=0.9\)
- calibration 使用完整 20 条 pool
- 固定 test 为 25 条
- calibrated threshold：`4.9996421406662925`
- 正确标注：`Y`、`S`
- 排除标注：`N`（False）、`U`（Unverifiable）

主要结论：

1. Claim filtering 能明显提高 retained claims 的正确性，但它优化的是“留下来的内容是否可靠”，不是“回答是否完整”。
2. 7 / 25 条 test 回答被完全删空；空响应没有 retained claim，但对用户没有信息价值。
3. 17 / 25 条 test 回答非空且所有 retained claims 都正确。
4. 1 / 25 条回答在过滤后仍保留 `N` claim，说明频率分数并不保证一定选对。
5. 高频 claim 更容易保留、低频 claim 更容易删除，但分数高低不绝对等于标注真假。
6. 当前阈值具有很高的“保留精度”，但正确 claim 的“召回率”很低：45 条 retained
   claims 中 44 条正确（97.8% precision），但 135 条 `Y/S` 中只保留了 44 条
   （32.6% recall）。

25 条 test 的互斥结果统计：

| 结果 | 数量 |
|---|---:|
| 非空且 retained claims 全对 | 17 |
| 空响应 | 7 |
| 非空但 retained claims 中含 `N` | 1 |
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

## 4. Claim 层面的定量分析

### 4.1 不同标注的保留情况

| 标注 | 总数 | 保留 | 删除 | 保留率 |
|---|---:|---:|---:|---:|
| `Y` Factual | 111 | 40 | 71 | 36.0% |
| `S` Subjective | 24 | 4 | 20 | 16.7% |
| `N` False | 52 | 1 | 51 | 1.9% |
| `U` Unverifiable | 23 | 0 | 23 | 0% |

这说明 frequency 与正确性有明确关系：`Y/S` 的保留率明显高于 `N/U`。但过滤非常
保守，把大多数正确 claim 也删掉了。

- 在全部 210 条 claim 中，原始 `Y/S` 比例是 64.3%。
- 过滤后 45 条 retained claims 中有 44 条正确，precision 约 97.8%。
- 但 135 条正确 claim 只召回 44 条，recall 约 32.6%。
- 75 条 `N/U` 中删除了 74 条，排除率约 98.7%。

因此当前方法的主要问题不是“保留了太多错误内容”，而是“为了避免错误，牺牲了
大量正确但支持不稳定的信息”。

### 4.2 不同 frequency score 的结果

| Frequency score | 正确 claim 总数 | 正确且保留 | 正确但删除 | `N/U` 总数 | `N/U` 保留 |
|---|---:|---:|---:|---:|---:|
| 5 | 66 | 44 | 22 | 2 | 1 |
| 4 | 12 | 0 | 12 | 1 | 0 |
| 1–3 | 45 | 0 | 45 | 29 | 0 |
| 0 | 2 | 0 | 2 | 19 | 0 |
| 负数 | 10 | 0 | 10 | 24 | 0 |

这里有两个关键原因。

第一，当前阈值是 `4.999642...`，略高于整数 `5`。因此并不是所有 5/5 支持的 claim
都会被保留：只有 `5 + noise >= threshold` 的 claim 才能通过。66 条正确且 score=5
的 claim 中有 22 条因为 `noise` 为负而删除。例如：

- “She is best known for ... *Hello, Dolly!*” 是 `Y`、score=5，但
  `noise=-0.000489`，最终分数是 `4.999511 < threshold`。
- “Doug Sheehan is an American actor.” 也是 `Y`、score=5，但
  `noise=-0.000715`，最终被删除。

`noise` 原本只用于打破并列；但当阈值落在 5 附近时，它实际上变成了决定 claim 去留
的随机边界。这是当前离散 5 分制、小 calibration set 和严格 90% 目标共同造成的。

第二，score=4 表示有且仅有 4/5 个替代回答支持该 claim，或等价的总分少 1。
当前阈值会删除全部 score=4 的 claim，其中包括 12 条正确 claim。例如
“Lees Knowles wrote several books on military matters”只有约 4 分，因此被删除。

### 4.3 哪些文本特征更容易出现在被误删的 claim 中

以下是多标签表面统计；一条 claim 可以同时属于多个类别，因此比例不能相加。

| 特征 | 正确且保留 | 正确但删除 | 观察 |
|---|---:|---:|---|
| 含具体数字 | 25.0% | 25.3% | 没有明显差异 |
| 含作品、事件或奖项 | 15.9% | 23.1% | 删除组更高 |
| 用 and / 分号连接多个事实 | 11.4% | 17.6% | 删除组更高 |
| 以 he/she/his/her/this/another 开头 | 6.8% | 18.7% | 删除组明显更高 |
| `S` 主观标注 | 9.1% | 22.0% | 主观 claim 更容易删除 |
| 含 could/might/unclear 等含糊词 | 11.4% | 8.8% | 差异不稳定 |

这些是描述性结果，不是因果证明，但和 frequency scoring 的工作方式一致。

### 4.4 容易误删正确 claim 的类型

#### 类型 A：替代回答没有提到的长尾细节

具体奖牌、书籍、电影、职位、出生地和年份不一定在每次自由生成中出现。没有被提到
通常记为 0，而不是 -1，因此 claim 会得到低分。

例如：

- “Sharad Kumar won a gold medal at the 2014 Asian Para Games.” 是 `Y`，但只有
  score=1。
- “Zamfir Ralli-Arbore was a historian.” 是 `Y`，但只有 score=3。

这不是因为 claim 错误，而是因为 5 个替代回答选择了不同细节。

#### 类型 B：一个 claim 包含多个事实

复合 claim 中只要一个成分缺失，LLM judge 就可能把它整体判为不支持。例如：

- “Sleepy John Estes was born in 1899 and died in 1977.” 同时包含出生和死亡，
  score=4，最终删除。
- “Sharad Kumar was born on March 1, 1992, in Bihar, India.” 同时包含日期和地点；
  虽然本例保留，但结构上更容易受到部分支持的影响。

上游虽然要求拆分“small, independent claims”，但实际缓存仍存在
`and`、地点与日期组合、职务与年份组合等多事实单元。

#### 类型 C：依赖代词或前文指代

“He was born in Yokohama”或“She participated in the World Championships”必须依赖
人物指代。替代回答如果换了句式或没有相同上下文，judge 可能判为 unrelated。

删除组中 18.7% 的 claim 以 he/she/his/her/this/another 开头，而保留组只有 6.8%。
例如：

- “He was born in Yokohama, Japan.” 是 `Y`，但 score=-2。
- “She has participated in the World Championships.” 是 `Y`，但 score=3。

#### 类型 D：实体有歧义

`John Estes`、`Carlos Alfonso` 这类 prompt 有多个同名人物。原回答会并列多个候选，
替代回答可能聚焦不同的人，claim judge 也会因指代对象变化而给低分。

例如“Another notable person ... Carlos Alfonso (baseball)”是 `Y`，但 score=-2。
被删掉的不是一句错误事实，而是一个对消歧很重要的候选实体。

#### 类型 E：主观或评价性陈述

`S` claim 常使用“known for”“successful”“charming”等表达。不同生成不会以相同方式
重复这些评价，judge 也更容易把它视为不直接支持。

- 24 条 `S` 中只有 4 条被保留，而 111 条 `Y` 中保留了 40 条。
- “Song Kang is known for his charming personality”是 `S`，score=1。
- “Díaz is known for her speed, agility, and determination”是 `S`，score=3。

#### 类型 F：关于回答过程本身的元陈述

“The assistant couldn't find information”“the name might be misspelled”在原始对话
语境中可能为真，但它们不是稳定的世界知识。新的独立采样没有必要重复这些内容，
因此 cross-sample support 很低。

- “The assistant couldn't find information on ...”是 `Y`，但 score=-1。
- “The name ... might have been misspelled”是 `N`，score=3。

这类 claim 说明：一个 statement 相对原回答上下文为真，不保证它在独立采样中可验证。

### 4.5 为什么错误 claim 也可能通过

Frequency score 衡量的是“5 个回答是否一致支持”，而不是“外部知识是否真实”。
因此它无法自动解决三种情况：

1. 5 个采样回答来自同一模型，会重复同样的错误。
2. LLM judge 可能接受一个与替代回答措辞相容、但事实错误或不可验证的 claim。
3. 人工标注与模型判断可能使用不同的判定标准或知识来源。

本 test set 只有一个 `N` claim 通过：

- “Rennie Fritchie is a British public servant.” score=5，最终保留，但缓存标注为 `N`。

这句话从常识看并不明显错误，因此它也可能是 annotation/source disagreement，而不能
只归因于模型重复幻觉。当前只有一个 false positive，样本不足以估计真实错误通过率。
但机制上，只要错误 claim 在多次回答中稳定出现，它就可能获得与正确 claim 相同的高分。

另有 Vincenzo Tusa 的职务 claim 是 `U`、score=5，最终仅因负 noise 被删除。这说明
高 frequency 代表“重复或可被 judge 匹配”，不等于已经通过外部事实核验。

### 4.6 对方法设计的启示

- 应分别报告 precision 和 recall，不能只看 “retained claims 全对”的比例。
- 应区分“替代回答明确反对”与“替代回答没有提到”两种零支持来源。
- Claim 应尽量拆成单一实体、单一谓词和单一数值，减少复合陈述。
- 对有歧义的人物名，应先消歧，再比较 claim。
- 5 次采样太粗，且同一模型的多次生成并不独立；增加采样数可降低离散阈值效应，
  但不能消除共同幻觉。
- 语义等价判断需要处理同义改写、指代和部分支持，而不是只做整句支持判断。

## 5. 成功案例

### 5.1 Sharad Kumar：删除错误奖牌，保留完整人物主线

- ID：`factscore-0027`
- Prompt：`Sharad Kumar (athlete)`
- 原始 claims：13
- `N + U` claims：5（`N=4`，`U=1`）
- 保留 claims：4
- `N + U` claims 保留数：0
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

### 5.2 Zamfir Arbore：过滤错误，但信息保留接近临界

- ID：`factscore-0049`
- Prompt：`Zamfir Arbore`
- 原始 claims：10
- `N + U` claims：3（`N=1`，`U=2`）
- 保留 claims：4
- `N + U` claims 保留数：0
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

- 一条 `N` 和两条 `U` 全部删除。
- “historian”其实正确，但 frequency score 只有约 3，被当作低置信信息删除。
- 这说明 filtering 的目标不是最大化信息量；它宁愿牺牲正确但低频的事实，也要
  降低保留错误内容的风险。

## 6. 事实正确但内容不足的案例

### 6.1 Rin Iwanaga：只剩“可能是普通人”

- ID：`factscore-0034`
- Prompt：`Rin Iwanaga`
- 原始 claims：5
- `N + U` claims：1（`N=1`，`U=0`）
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

### 6.2 Carlos Alfonso：只留下一个同名候选

- ID：`factscore-0046`
- Prompt：`Carlos Alfonso`
- 原始 claims：8
- `N + U` claims：1（`N=1`，`U=0`）
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

## 7. 完全删空的案例

### 7.1 Luis Guillermo Rivera

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

### 7.2 Roxana Díaz

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

## 8. 过滤失败的案例

### 8.1 Rennie Fritchie：高分错误 claim 被保留

- ID：`factscore-0047`
- 原始 claims：8
- `N + U` claims：3（`N=3`，`U=0`）
- 保留 claims：3
- 保留的 `N + U` claims：1（`N=1`，`U=0`）
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

## 9. 对 Part 2 问题的回答

### 9.1 为什么长回答需要 claim filtering

长回答通常同时包含正确和错误 statement。Sharad Kumar 和 Zamfir Arbore 案例显示，
过滤可以删除错误奖牌、党派或身份 claim，使保留内容更可靠。

### 9.2 过滤是否会让回答正确但不完整

会。最直接的是 7 条空响应。Rin Iwanaga 和 Carlos Alfonso 还展示了非空但不完整的
情况：留下内容正确，却不足以提供人物简介或解释名字歧义。

### 9.3 如果重复采样一直得不到正确答案

本实验使用仓库缓存好的 frequency score，没有重新执行 5 次采样，因此不能在当前
数据上精确复现“五次都没有正确回答”的过程。Luis Guillermo Rivera 和 Roxana Díaz
的低分正确 claim 说明，即使存在正确内容，只要其跨回答支持不足，也可能被全部删除。
更直接的采样失败分析需要后续保存原采样输出。

### 9.4 Coverage 与 factuality 为什么不能互换

- ConU 的 coverage 问：答案集合是否至少包含一个正确答案。
- Factuality 问：一段回答中保留下来的 claims 是否都正确。

一个空回答没有错误 claim，但也没有回答；一个包含 3 个答案的集合可能覆盖正确答案，
同时也包含错误答案。两者衡量的是不同对象，不能直接比较数值大小。

## 10. 审阅时建议重点判断

1. Zamfir Arbore 是否算“成功”还是“信息不足”，是本报告最依赖人工判断的边界案例。
2. Rin Iwanaga 和 Carlos Alfonso 的“不足以回答”判断是否合理。
3. Rennie Fritchie 的 `N` 标注是否可信；如果不信，应把它归为 annotation-quality
   case，而不是单纯 filtering failure。
4. 当前只分析 claim 保留情况，没有重新生成流畅 answer。报告中应明确这一点。

## 11. 复现

```bash
PYTHONPATH=src .venv/bin/python -m confqa.factuality.cli cases \
    --config configs/factuality.yaml
```

该命令输出主设置阈值、25 条 test 的三类结果计数和缓存排除审计。
