# Флоу пользователя в боте

Документ описывает полный путь пользователя (кандидат и менеджер) от входа до обмена контактами. По нему можно проверить, что все шаги реализованы.

---

## 1. Вход и онбординг

| Шаг | Действие пользователя | Состояние до → после | Что делает бот |
|-----|------------------------|----------------------|----------------|
| 1.1 | `/start` или рестарт | — → `role_selection`, `awaitingContactChoice: true` | Приветствие + просьба поделиться контактом (кнопки Share / Skip). |
| 1.2 | Share contact (кнопка или номер в тексте) | — | Сохраняет контакт в БД, снимает `awaitingContactChoice`. Показывает выбор роли. |
| 1.3 | Skip for now | — | Убирает клавиатуру контакта, показывает выбор роли. |
| 1.4 | Выбор роли: **Candidate** (кнопка или текст) | `role_selection` → `onboarding_candidate` → `waiting_resume` | Онбординг кандидата + просьба прислать резюме (текст или файл). |
| 1.5 | Выбор роли: **Hiring / Manager** (кнопка или текст) | `role_selection` → `onboarding_manager` → `waiting_job` | Онбординг менеджера + просьба прислать описание вакансии. |

**Файлы:** `state.router.ts` (restartFlow, startRoleFlowFromText), `callback.router.ts` (CALLBACK_ROLE_*), `state.service.ts` (reset, getOrCreate), `transition-rules.ts`.

---

## 2. Кандидат: документ и прескрин

| Шаг | Действие | Состояние до → после | Что делает бот |
|-----|-----------|----------------------|----------------|
| 2.1 | Текст/файл с резюме в `waiting_resume` | `waiting_resume` → `extracting_resume` | «Обрабатываю…», извлечение текста, сохранение в сессию и БД. |
| 2.2 | Успешная обработка | `extracting_resume` → `interviewing_candidate` | Генерация плана прескрина (v1 или v2), первый вопрос. |
| 2.3 | Ответ на вопрос (текст/голос) | — | Интерпретация ответа, сохранение фактов, следующий вопрос или завершение. |
| 2.4 | Завершение прескрина | `interviewing_candidate` → `candidate_profile_ready` | Сохранение профиля, переход к обязательным полям. |
| 2.5 | Обязательные поля (location, work_mode, salary) | `candidate_profile_ready` → `candidate_mandatory_fields` → … | Вопросы по локации, формату работы, зарплате (с ретраями при невалидном вводе). |
| 2.6 | Все mandatory заполнены | `candidate_mandatory_fields` → `candidate_profile_ready` | Сообщение о готовности + кнопки «Find jobs» / «Pause matching» и т.д. |

**Файлы:** `state.router.ts` (handleDocumentUpdate, handlePastedDocumentText, handleInterviewAnswer, startCandidateMandatoryFieldsFlow), `interview.engine.ts`, `candidate-prescreen.engine.ts` (v2), `transition-rules.ts`.

---

## 3. Менеджер: вакансия и прескрин

| Шаг | Действие | Состояние до → после | Что делает бот |
|-----|-----------|----------------------|----------------|
| 3.1 | Текст/файл с вакансией в `waiting_job` | `waiting_job` → `extracting_job` | «Обрабатываю…», извлечение текста, сохранение в БД. |
| 3.2 | Успешная обработка | `extracting_job` → `interviewing_manager` | План прескрина по вакансии (v1/v2), первый вопрос. |
| 3.3 | Ответы на вопросы | — | Аналогично кандидату: интерпретация, факты, следующий вопрос. |
| 3.4 | Завершение прескрина | `interviewing_manager` → `job_profile_ready` | Профиль вакансии сохранён. |
| 3.5 | Обязательные поля (work_format, countries, budget) | `job_profile_ready` → `manager_mandatory_fields` → … | Вопросы по формату, странам, бюджету. |
| 3.6 | Все mandatory заполнены | `manager_mandatory_fields` → `job_published` | Вакансия опубликована, менеджер может смотреть кандидатов. |

**Файлы:** `state.router.ts` (handleDocumentUpdate, handlePastedDocumentText, startManagerMandatoryFieldsFlow), `job-prescreen.engine.ts` (v2), `transition-rules.ts`.

---

## 4. Матчинг по запросу (Stage 10)

Триггер: текст («find jobs», «match me», «покажи кандидатов» и т.п.) или LLM intent `request_matching`. Либо кнопка «Find jobs» / аналог.

| Роль | Условие | Действие бота |
|------|---------|----------------|
| Кандидат | Профиль не готов (mandatory не заполнены) | Спросить одно недостающее поле, затем можно снова запросить матчинг. |
| Кандидат | Профиль готов | `MatchingEngine.getMatchRecordsForCandidate` → до 3 карточек вакансий с кнопками Apply / Reject (и текст «apply»/«reject» через intent). |
| Менеджер | Нет активной вакансии | Выбор активной вакансии (lastActiveJobId или выбор из последних). |
| Менеджер | Вакансия есть, mandatory не готовы | Спросить одно недостающее поле. |
| Менеджер | Всё готово | `MatchingEngine.getMatchRecordsForManager` → до 3 карточек кандидатов с Accept / Reject. |

Карточки формируются через `MatchCardComposerService` (LLM, match_card_compose_v3). В сессии обновляется `matching.lastShownMatchIds` и `lastActionableMatchId` для текстовых apply/reject.

**Файлы:** `dialogue.orchestrator.ts` (handleRequestMatching), `matching.engine.ts` (getMatchRecordsForCandidate, getMatchRecordsForManager), `match-card-composer.service.ts`, `state.router.ts` (обработка result.matchCards и result.matchAction).

---

## 5. Решения по матчу

| Действие | Кто | Состояние матча | Что происходит |
|----------|-----|------------------|----------------|
| **Apply** (кнопка или текст) | Кандидат | `proposed` → `candidate_applied` | Уведомление менеджеру, кандидат остаётся в `candidate_profile_ready`. |
| **Reject** (кнопка или текст) | Кандидат | `proposed` → `candidate_rejected` | Подтверждение, при необходимости переход в `candidate_profile_ready`. |
| **Accept** (кнопка или текст) | Менеджер | `candidate_applied` → `manager_accepted` | Подтверждение менеджеру; кандидату — запрос согласия на обмен контактом (consent flow). |
| **Reject** (кнопка или текст) | Менеджер | `candidate_applied` → `manager_rejected` | Уведомление кандидату, переход менеджера в `job_published`. |

Текстовые «apply»/«reject»/«accept» обрабатываются через intent в `dialogue.orchestrator.ts` (handleMatchAction) и выполняются в `callback.router.executeMatchAction`.

**Файлы:** `callback.router.ts` (handleCandidateApply, handleCandidateReject, handleManagerAccept, handleManagerReject, executeMatchAction), `decision.service.ts`, `match-storage.service.ts`.

---

## 6. Consent-based обмен контактами (Stage 10)

После **Accept** менеджером:

| Шаг | Кому | Действие | Результат |
|-----|------|----------|-----------|
| 6.1 | Кандидат | Сообщение: «Менеджер заинтересован. Поделиться Telegram-контактом?» + Share / Not now | Ожидание выбора. |
| 6.2 | Кандидат нажимает **Share** | Кандидат согласился | Менеджеру: «Кандидат согласился. Поделиться своим контактом?» + Share / Not now. |
| 6.3 | Кандидат нажимает **Not now** | — | Сообщение кандидату, статус матча остаётся `manager_accepted`. |
| 6.4 | Менеджер нажимает **Share** | Оба согласны | `ContactExchangeService.prepareExchange` → `notifyContactsShared` → каждому отправляется контакт другого, статус матча → `contact_shared`, состояния пользователей → `contact_shared`. |
| 6.5 | Менеджер нажимает **Not now** | — | Сообщение менеджеру, статус остаётся `manager_accepted`. |

**Файлы:** `callback.router.ts` (handleConsentCandidateShare, handleConsentCandidateNo, handleConsentManagerShare, handleConsentManagerNo), `contact-exchange.service.ts`, `notification.engine.ts` (notifyContactsShared), `decision.service.ts` (markContactShared).

---

## 7. Уведомления о матчах (без явного запроса)

| Событие | Кому | Переход состояния | Действие |
|---------|------|--------------------|----------|
| Новый матч для кандидата (автомат/воркер) | Кандидат | → `waiting_candidate_decision` | Первый раз — объяснение матчинга, затем карточка вакансии с Apply/Reject. Учитываются rate limit и auto_notify. |
| Кандидат нажал Apply | Менеджер | → `waiting_manager_decision` | Карточка кандидата с Accept/Reject. |
| Менеджер нажал Reject | Кандидат | → `candidate_profile_ready` | Уведомление об отказе. |
| Оба поделились контактом | Оба | → `contact_shared` | Каждому отправлен контакт второго. |

**Файлы:** `notification.engine.ts` (notifyCandidateOpportunity, notifyManagerCandidateApplied, notifyManagerRejected, notifyContactsShared), `transition-rules.ts`.

---

## 8. Прочие сценарии

| Сценарий | Поведение |
|----------|-----------|
| **Удаление данных** | Текст «delete my data» и т.п. → подтверждение (кнопки) → удаление контакта и данных, рестарт флоу. |
| **Смена языка** | Текст вроде «English only» → ответ на английском, в сессии `preferredLanguage: "en"`. |
| **Повтор одного и того же ответа (repeat loop)** | Сообщение-подсказка (skip/move on), без дублирования ответа. |
| **Голосовые сообщения** | Транскрипция (Whisper), текст обрабатывается как ответ на текущий вопрос или как обычное сообщение в диалоге. |
| **Диалог v2 (LLM always-on)** | В состояниях прескрина/профиля/матчинга текст пользователя идёт через `DialogueOrchestratorV2`: интенты (answer, skip, request_matching, match_apply, match_reject, smalltalk и т.д.) и ответ через Reply Composer. |
| **Админ-команды** | `/debug_chat_id`, `/debug_state`, `/debug_profile`, `/debug_last_route`, `/debug_matches`, `/debug_failures` — только для `ADMIN_USER_IDS`. |

**Файлы:** `state.router.ts` (data deletion, admin debug, classifyAlwaysOnForUpdate), `dialogue.orchestrator.ts`, `intent-router-v2.service.ts`, `telegram.client.ts` (голос, транскрипция).

---

## 9. Состояния (UserState) — сводка

| Состояние | Роль | Смысл |
|-----------|------|--------|
| `role_selection` | Обе | Выбор роли после контакта. |
| `onboarding_candidate` / `onboarding_manager` | Кандидат / Менеджер | Онбординг перед приёмом документа. |
| `waiting_resume` / `waiting_job` | Кандидат / Менеджер | Ожидание резюме / описания вакансии. |
| `extracting_resume` / `extracting_job` | Кандидат / Менеджер | Обработка документа. |
| `interviewing_candidate` / `interviewing_manager` | Кандидат / Менеджер | Прескрин (вопросы). |
| `candidate_profile_ready` / `job_profile_ready` | Кандидат / Менеджер | Профиль готов, дальше mandatory или матчинг. |
| `candidate_mandatory_fields` / `manager_mandatory_fields` | Кандидат / Менеджер | Заполнение обязательных полей. |
| `job_published` | Менеджер | Вакансия опубликована, можно смотреть кандидатов. |
| `waiting_candidate_decision` | Кандидат | Показана карточка матча, ждём Apply/Reject. |
| `waiting_manager_decision` | Менеджер | Показана карточка кандидата, ждём Accept/Reject. |
| `contact_shared` | Обе | Контакты обменяны по матчу. |

Переходы заданы в `src/state/transition-rules.ts`.

---

## 10. Чеклист: всё ли сделано

- [ ] **Вход:** `/start` → контакт → выбор роли → переход в `waiting_resume` / `waiting_job`.
- [ ] **Кандидат:** приём резюме (текст/файл) → extracting → interviewing → candidate_profile_ready → mandatory (location, work_mode, salary) → снова candidate_profile_ready с кнопками.
- [ ] **Менеджер:** приём вакансии → extracting → interviewing → job_profile_ready → mandatory (work_format, countries, budget) → job_published.
- [ ] **Матчинг по запросу:** текст/кнопка «find jobs» / «покажи кандидатов» → проверка профиля и mandatory → до 3 карточек с Apply/Reject (кандидат) или Accept/Reject (менеджер).
- [ ] **Текстовые apply/reject/accept:** intent в диалоге → executeMatchAction, обновление статуса матча и уведомления.
- [ ] **Consent после Accept:** кандидату Share/Not now → менеджеру Share/Not now → при обоих Share — обмен контактами и переход в contact_shared.
- [ ] **Уведомления:** авто-матч → waiting_candidate_decision / waiting_manager_decision; Apply → уведомление менеджеру; Reject менеджера → уведомление кандидату; обмен контактами → notifyContactsShared и contact_shared.
- [ ] **Повтор ответа:** не дублировать, отправить подсказку (skip/move on).
- [ ] **Удаление данных:** запрос → подтверждение → удаление и рестарт.
- [ ] **Админ:** debug-команды только для ADMIN_USER_IDS.

Если все пункты выполняются в текущей сборке — флоу считается реализованным.
