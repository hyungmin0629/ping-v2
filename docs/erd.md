# ERD

> ⚠️ **이 파일은 생성물이다. 손으로 고치지 마라.**
> 살아 있는 스키마에서 뽑는다 — `python db/erd.py`
>
> 관계는 실제로 걸려 있는 FK 만 나온다. 컬럼은 **키(PK·FK)만** 싣는다.
> 전체 컬럼 정의는 `db/ddl/` 이 진실이다.

테이블 **42개** · FK **77개**

점선(`|o`)으로 시작하는 관계는 FK 가 NULL 을 허용한다는 뜻이다.

## 전체

42개를 한 장에 놓은 것이다. 색이 도메인이고, 화살표는 자식 → 부모다.
같은 두 테이블 사이에 FK 가 여럿이면 선 하나로 접고 `×N` 을 붙였다.

```mermaid
flowchart LR
    subgraph g0["기준 정보"]
        direction TB
        region[region]
        school[school]
        grade_class[grade_class]
        admin_user[admin_user]
    end
    subgraph g1["유저"]
        direction TB
        app_user[app_user]
        user_session[user_session]
        user_withdrawal[user_withdrawal]
        withdrawal_reason[withdrawal_reason]
    end
    subgraph g2["친구"]
        direction TB
        friend_request[friend_request]
        friendship[friendship]
        friend_recommendation[friend_recommendation]
        block_record[block_record]
    end
    subgraph g3["질문과 투표"]
        direction TB
        question_category[question_category]
        question[question]
        question_request[question_request]
        vote_session[vote_session]
        vote_item[vote_item]
        vote_candidate[vote_candidate]
        vote_shuffle[vote_shuffle]
        vote_received[vote_received]
        hint_purchase[hint_purchase]
        ad_impression[ad_impression]
    end
    subgraph g4["하트"]
        direction TB
        heart_transaction_type[heart_transaction_type]
        heart_product[heart_product]
        heart_purchase[heart_purchase]
        heart_transaction[heart_transaction]
    end
    subgraph g5["신고와 제재"]
        direction TB
        report_reason[report_reason]
        report[report]
        sanction_policy[sanction_policy]
        sanction[sanction]
    end
    subgraph g6["학교 정보"]
        direction TB
        meal_plan[meal_plan]
        meal_menu_item[meal_menu_item]
        timetable[timetable]
        school_notice[school_notice]
        school_notice_read[school_notice_read]
        school_event[school_event]
        external_sync_log[external_sync_log]
    end
    subgraph g7["게시판"]
        direction TB
        board_category[board_category]
        post[post]
        post_comment[post_comment]
        post_like[post_like]
        comment_like[comment_like]
    end
    ad_impression --> app_user
    admin_user --> school
    app_user --> grade_class
    block_record -->|"×2"| app_user
    comment_like --> app_user
    comment_like --> post_comment
    external_sync_log --> school
    friend_recommendation -->|"×2"| app_user
    friend_request -->|"×2"| app_user
    friendship -->|"×2"| app_user
    grade_class --> school
    heart_purchase --> app_user
    heart_purchase --> heart_product
    heart_transaction --> ad_impression
    heart_transaction --> admin_user
    heart_transaction --> app_user
    heart_transaction --> heart_purchase
    heart_transaction --> heart_transaction_type
    heart_transaction --> hint_purchase
    heart_transaction --> vote_item
    hint_purchase --> app_user
    hint_purchase --> vote_received
    meal_menu_item --> meal_plan
    meal_plan --> school
    post --> app_user
    post --> board_category
    post --> school
    post_comment --> app_user
    post_comment --> post
    post_comment --> post_comment
    post_like --> app_user
    post_like --> post
    question --> admin_user
    question --> question_category
    question_request --> admin_user
    question_request --> app_user
    question_request --> question
    question_request --> question_category
    report --> admin_user
    report -->|"×2"| app_user
    report --> post
    report --> post_comment
    report --> question
    report --> report_reason
    sanction --> admin_user
    sanction --> app_user
    sanction --> report
    sanction --> sanction_policy
    school --> region
    school --> school
    school_event --> school
    school_notice --> admin_user
    school_notice --> school
    school_notice_read --> app_user
    school_notice_read --> school_notice
    timetable --> grade_class
    user_session --> app_user
    user_withdrawal --> app_user
    user_withdrawal --> withdrawal_reason
    vote_candidate --> app_user
    vote_candidate --> vote_item
    vote_item --> app_user
    vote_item --> question
    vote_item --> vote_session
    vote_received -->|"×2"| app_user
    vote_received --> question
    vote_received --> vote_item
    vote_session --> app_user
    vote_shuffle --> ad_impression
    vote_shuffle --> vote_item
    classDef c0 fill:#E3E8E6,stroke:#5C6B6B,color:#14181A
    class region,school,grade_class,admin_user c0
    classDef c1 fill:#CFE6DE,stroke:#5C6B6B,color:#14181A
    class app_user,user_session,user_withdrawal,withdrawal_reason c1
    classDef c2 fill:#DCE7CF,stroke:#5C6B6B,color:#14181A
    class friend_request,friendship,friend_recommendation,block_record c2
    classDef c3 fill:#E9E2CB,stroke:#5C6B6B,color:#14181A
    class question_category,question,question_request,vote_session,vote_item,vote_candidate,vote_shuffle,vote_received,hint_purchase,ad_impression c3
    classDef c4 fill:#F0DCCB,stroke:#5C6B6B,color:#14181A
    class heart_transaction_type,heart_product,heart_purchase,heart_transaction c4
    classDef c5 fill:#EED6D6,stroke:#5C6B6B,color:#14181A
    class report_reason,report,sanction_policy,sanction c5
    classDef c6 fill:#D6E0EE,stroke:#5C6B6B,color:#14181A
    class meal_plan,meal_menu_item,timetable,school_notice,school_notice_read,school_event,external_sync_log c6
    classDef c7 fill:#E2D9EA,stroke:#5C6B6B,color:#14181A
    class board_category,post,post_comment,post_like,comment_like c7
```

## 기준 정보

지역·학교·학급. 유저를 배치할 곳이 먼저 있어야 한다.

```mermaid
erDiagram
    region {
        bigint id PK
    }
    school {
        bigint id PK
        bigint info_school_id FK
        bigint region_id FK
    }
    grade_class {
        bigint id PK
        bigint school_id FK
    }
    admin_user {
        bigint id PK
        bigint school_id FK
    }
    school |o--o{ admin_user : "school_id"
    school ||--o{ grade_class : "school_id"
    school |o--o{ school : "info_school_id"
    region ||--o{ school : "region_id"
```

## 유저

익명 계정 하나에 프로필 하나. 접속 기록과 탈퇴가 딸린다.

```mermaid
erDiagram
    app_user {
        uuid auth_user_id FK
        bigint class_id FK
        bigint id PK
    }
    user_session {
        bigint id PK
        bigint user_id FK
    }
    user_withdrawal {
        bigint id PK
        varchar reason_code FK
        bigint user_id FK
    }
    withdrawal_reason {
        varchar code PK
    }
    app_user ||--o{ user_session : "user_id"
    withdrawal_reason ||--o{ user_withdrawal : "reason_code"
    app_user ||--o{ user_withdrawal : "user_id"
```

## 친구

요청(방향 있음) → 수락 → friendship(방향 없음).

```mermaid
erDiagram
    friend_request {
        bigint id PK
        bigint receiver_id FK
        bigint sender_id FK
    }
    friendship {
        bigint id PK
        bigint user_high_id FK
        bigint user_low_id FK
    }
    friend_recommendation {
        bigint id PK
        bigint recommended_user_id FK
        bigint user_id FK
    }
    block_record {
        bigint blocked_user_id FK
        bigint id PK
        bigint user_id FK
    }
```

## 질문과 투표

세션 하나에 아이템 여럿, 아이템 하나에 후보 넷.

```mermaid
erDiagram
    question_category {
        bigint id PK
    }
    question {
        bigint category_id FK
        bigint created_by_admin_id FK
        bigint id PK
    }
    question_request {
        bigint id PK
        bigint proposed_category_id FK
        bigint published_question_id FK
        bigint reviewed_by_admin_id FK
        bigint user_id FK
    }
    vote_session {
        bigint id PK
        bigint user_id FK
    }
    vote_item {
        bigint id PK
        bigint question_id FK
        bigint session_id FK
        bigint user_id FK
    }
    vote_candidate {
        bigint candidate_user_id FK
        bigint id PK
        bigint vote_item_id FK
    }
    vote_shuffle {
        bigint ad_impression_id FK
        bigint id PK
        bigint vote_item_id FK
    }
    vote_received {
        bigint id PK
        bigint question_id FK
        bigint receiver_id FK
        bigint vote_item_id FK
        bigint voter_id FK
    }
    hint_purchase {
        bigint id PK
        bigint user_id FK
        bigint vote_received_id FK
    }
    ad_impression {
        bigint id PK
        bigint user_id FK
    }
    vote_received ||--o{ hint_purchase : "vote_received_id"
    question_category ||--o{ question : "category_id"
    question_category |o--o{ question_request : "proposed_category_id"
    question |o--o{ question_request : "published_question_id"
    vote_item ||--o{ vote_candidate : "vote_item_id"
    question ||--o{ vote_item : "question_id"
    vote_session ||--o{ vote_item : "session_id"
    question ||--o{ vote_received : "question_id"
    vote_item ||--o{ vote_received : "vote_item_id"
    ad_impression ||--o{ vote_shuffle : "ad_impression_id"
    vote_item ||--o{ vote_shuffle : "vote_item_id"
```

## 하트

모든 증감이 heart_transaction 하나를 거친다. 이 프로젝트의 핵심.

```mermaid
erDiagram
    heart_transaction_type {
        varchar code PK
    }
    heart_product {
        bigint id PK
    }
    heart_purchase {
        bigint id PK
        bigint product_id FK
        bigint user_id FK
    }
    heart_transaction {
        bigint ad_impression_id FK
        bigint admin_id FK
        bigint hint_purchase_id FK
        bigint id PK
        bigint purchase_id FK
        varchar type_code FK
        bigint user_id FK
        bigint vote_item_id FK
    }
    heart_product ||--o{ heart_purchase : "product_id"
    heart_purchase |o--o{ heart_transaction : "purchase_id"
    heart_transaction_type ||--o{ heart_transaction : "type_code"
```

## 신고와 제재

신고와 제재를 FK 로 연결한다. 구 시스템에는 이 연결이 없었다.

```mermaid
erDiagram
    report_reason {
        varchar code PK
    }
    report {
        bigint id PK
        varchar reason_code FK
        bigint reporter_id FK
        bigint reviewed_by_admin_id FK
        bigint target_comment_id FK
        bigint target_post_id FK
        bigint target_question_id FK
        bigint target_user_id FK
    }
    sanction_policy {
        bigint id PK
    }
    sanction {
        bigint id PK
        bigint issued_by_admin_id FK
        bigint policy_id FK
        bigint triggered_by_report_id FK
        bigint user_id FK
    }
    report_reason ||--o{ report : "reason_code"
    sanction_policy |o--o{ sanction : "policy_id"
    report |o--o{ sanction : "triggered_by_report_id"
```

## 학교 정보

NEIS 에서 받아 채운다. 급식은 데이터를 준 학교 아래 저장한다.

```mermaid
erDiagram
    meal_plan {
        bigint id PK
        bigint school_id FK
    }
    meal_menu_item {
        bigint id PK
        bigint meal_plan_id FK
    }
    timetable {
        bigint class_id FK
        bigint id PK
    }
    school_notice {
        bigint created_by_admin_id FK
        bigint id PK
        bigint school_id FK
    }
    school_notice_read {
        bigint id PK
        bigint notice_id FK
        bigint user_id FK
    }
    school_event {
        bigint id PK
        bigint school_id FK
    }
    external_sync_log {
        bigint id PK
        bigint school_id FK
    }
    meal_plan ||--o{ meal_menu_item : "meal_plan_id"
    school_notice ||--o{ school_notice_read : "notice_id"
```

## 게시판

자유게시판(W9). 익명이 아니라 글쓴이가 드러난다.

```mermaid
erDiagram
    board_category {
        bigint id PK
    }
    post {
        bigint author_id FK
        bigint category_id FK
        bigint id PK
        bigint school_id FK
    }
    post_comment {
        bigint author_id FK
        bigint id PK
        bigint parent_comment_id FK
        bigint post_id FK
    }
    post_like {
        bigint id PK
        bigint post_id FK
        bigint user_id FK
    }
    comment_like {
        bigint comment_id FK
        bigint id PK
        bigint user_id FK
    }
    post_comment ||--o{ comment_like : "comment_id"
    board_category ||--o{ post : "category_id"
    post_comment |o--o{ post_comment : "parent_comment_id"
    post ||--o{ post_comment : "post_id"
    post ||--o{ post_like : "post_id"
```

## 도메인을 넘는 연결

도표를 읽을 수 있게 위 그림에서는 뺐다. 실제로는 걸려 있는 FK 다.

| 자식 | 컬럼 | 부모 |
|---|---|---|
| comment_like <sub>(게시판)</sub> | `user_id` | app_user <sub>(유저)</sub> |
| post <sub>(게시판)</sub> | `author_id` | app_user <sub>(유저)</sub> |
| post <sub>(게시판)</sub> | `school_id` | school <sub>(기준 정보)</sub> |
| post_comment <sub>(게시판)</sub> | `author_id` | app_user <sub>(유저)</sub> |
| post_like <sub>(게시판)</sub> | `user_id` | app_user <sub>(유저)</sub> |
| report <sub>(신고와 제재)</sub> | `reporter_id` | app_user <sub>(유저)</sub> |
| report <sub>(신고와 제재)</sub> | `reviewed_by_admin_id` | admin_user <sub>(기준 정보)</sub> |
| report <sub>(신고와 제재)</sub> | `target_comment_id` | post_comment <sub>(게시판)</sub> |
| report <sub>(신고와 제재)</sub> | `target_post_id` | post <sub>(게시판)</sub> |
| report <sub>(신고와 제재)</sub> | `target_question_id` | question <sub>(질문과 투표)</sub> |
| report <sub>(신고와 제재)</sub> | `target_user_id` | app_user <sub>(유저)</sub> |
| sanction <sub>(신고와 제재)</sub> | `issued_by_admin_id` | admin_user <sub>(기준 정보)</sub> |
| sanction <sub>(신고와 제재)</sub> | `user_id` | app_user <sub>(유저)</sub> |
| app_user <sub>(유저)</sub> | `auth_user_id` | auth.users <sub>(스키마 밖)</sub> |
| app_user <sub>(유저)</sub> | `class_id` | grade_class <sub>(기준 정보)</sub> |
| ad_impression <sub>(질문과 투표)</sub> | `user_id` | app_user <sub>(유저)</sub> |
| hint_purchase <sub>(질문과 투표)</sub> | `user_id` | app_user <sub>(유저)</sub> |
| question <sub>(질문과 투표)</sub> | `created_by_admin_id` | admin_user <sub>(기준 정보)</sub> |
| question_request <sub>(질문과 투표)</sub> | `reviewed_by_admin_id` | admin_user <sub>(기준 정보)</sub> |
| question_request <sub>(질문과 투표)</sub> | `user_id` | app_user <sub>(유저)</sub> |
| vote_candidate <sub>(질문과 투표)</sub> | `candidate_user_id` | app_user <sub>(유저)</sub> |
| vote_item <sub>(질문과 투표)</sub> | `user_id` | app_user <sub>(유저)</sub> |
| vote_received <sub>(질문과 투표)</sub> | `receiver_id` | app_user <sub>(유저)</sub> |
| vote_received <sub>(질문과 투표)</sub> | `voter_id` | app_user <sub>(유저)</sub> |
| vote_session <sub>(질문과 투표)</sub> | `user_id` | app_user <sub>(유저)</sub> |
| block_record <sub>(친구)</sub> | `blocked_user_id` | app_user <sub>(유저)</sub> |
| block_record <sub>(친구)</sub> | `user_id` | app_user <sub>(유저)</sub> |
| friend_recommendation <sub>(친구)</sub> | `recommended_user_id` | app_user <sub>(유저)</sub> |
| friend_recommendation <sub>(친구)</sub> | `user_id` | app_user <sub>(유저)</sub> |
| friend_request <sub>(친구)</sub> | `receiver_id` | app_user <sub>(유저)</sub> |
| friend_request <sub>(친구)</sub> | `sender_id` | app_user <sub>(유저)</sub> |
| friendship <sub>(친구)</sub> | `user_high_id` | app_user <sub>(유저)</sub> |
| friendship <sub>(친구)</sub> | `user_low_id` | app_user <sub>(유저)</sub> |
| heart_purchase <sub>(하트)</sub> | `user_id` | app_user <sub>(유저)</sub> |
| heart_transaction <sub>(하트)</sub> | `ad_impression_id` | ad_impression <sub>(질문과 투표)</sub> |
| heart_transaction <sub>(하트)</sub> | `admin_id` | admin_user <sub>(기준 정보)</sub> |
| heart_transaction <sub>(하트)</sub> | `hint_purchase_id` | hint_purchase <sub>(질문과 투표)</sub> |
| heart_transaction <sub>(하트)</sub> | `user_id` | app_user <sub>(유저)</sub> |
| heart_transaction <sub>(하트)</sub> | `vote_item_id` | vote_item <sub>(질문과 투표)</sub> |
| external_sync_log <sub>(학교 정보)</sub> | `school_id` | school <sub>(기준 정보)</sub> |
| meal_plan <sub>(학교 정보)</sub> | `school_id` | school <sub>(기준 정보)</sub> |
| school_event <sub>(학교 정보)</sub> | `school_id` | school <sub>(기준 정보)</sub> |
| school_notice <sub>(학교 정보)</sub> | `created_by_admin_id` | admin_user <sub>(기준 정보)</sub> |
| school_notice <sub>(학교 정보)</sub> | `school_id` | school <sub>(기준 정보)</sub> |
| school_notice_read <sub>(학교 정보)</sub> | `user_id` | app_user <sub>(유저)</sub> |
| timetable <sub>(학교 정보)</sub> | `class_id` | grade_class <sub>(기준 정보)</sub> |
