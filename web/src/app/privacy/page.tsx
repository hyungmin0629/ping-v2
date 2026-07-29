import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "개인정보처리방침 · ping",
  description: "ping 이 수집하는 정보와 처리 방침",
};

/**
 * 개인정보처리방침.
 *
 * 이 서비스는 이름·이메일·전화번호를 받지 않지만, 닉네임·성별·소속 조합은
 * 소규모 집단에서 개인을 특정할 수 있다. 그래서 "개인정보가 아니다"라고
 * 단정하지 않고 수집 항목과 목적을 명시한다.
 *
 * ⚠️ 법률 자문이 아니다. 클로즈드 테스트 범위에서 필요한 고지를 담은 것이고,
 *    공개 서비스로 전환하면 다시 검토해야 한다.
 */
const UPDATED_AT = "2026년 7월 29일";

export default function PrivacyPage() {
  return (
    <main className="mx-auto flex min-h-dvh w-full max-w-2xl flex-col gap-8 px-6 py-16">
      <header className="flex flex-col gap-2">
        <h1 className="text-2xl font-semibold tracking-tight">개인정보처리방침</h1>
        <p className="text-sm text-neutral-500">최종 수정일 {UPDATED_AT}</p>
      </header>

      <p className="text-sm leading-relaxed text-neutral-600 dark:text-neutral-400">
        ping(이하 &lsquo;서비스&rsquo;)은 지인 대상 <strong>비공개 시험 운영</strong> 중인
        서비스입니다. 상용 서비스가 아니며, 아래에 적힌 것 외의 정보는 수집하지
        않습니다.
      </p>

      <Section title="1. 수집하는 정보">
        <Table
          rows={[
            ["닉네임", "친구에게 표시되는 이름. 이용자가 직접 정합니다"],
            ["성별", "받은 투표에서 힌트로 공개되는 항목"],
            ["소속", "학교와 반. 투표 후보를 정하는 기준"],
            [
              "이용 기록",
              "투표·하트·친구 관계·접속 시각. 서비스 동작과 이용 분석에 쓰입니다",
            ],
            [
              "익명 계정 식별자",
              "브라우저에 발급되는 임의의 값. 개인을 알아볼 수 있는 정보가 아닙니다",
            ],
          ]}
        />
        <p className="text-sm leading-relaxed text-neutral-600 dark:text-neutral-400">
          <strong>수집하지 않습니다</strong> — 이름, 이메일, 전화번호, 비밀번호,
          생년월일, 연락처, 위치정보, 결제정보.
        </p>
        <p className="text-sm leading-relaxed text-neutral-600 dark:text-neutral-400">
          다만 <strong>닉네임·성별·소속의 조합은 소규모 집단에서 특정 개인을 알아볼
          수 있습니다.</strong> 서비스는 이를 개인정보로 간주하고 이 방침에 따라
          다룹니다.
        </p>
      </Section>

      <Section title="2. 이용 목적">
        <List
          items={[
            "친구 맺기, 투표, 하트 지급·차감 등 서비스 기능 제공",
            "서비스가 의도대로 동작하는지 확인하기 위한 이용 분석",
          ]}
        />
        <p className="text-sm leading-relaxed text-neutral-600 dark:text-neutral-400">
          광고에 활용하거나 제3자에게 판매하지 않습니다.
        </p>
      </Section>

      <Section title="3. 만 14세 미만 가입 제한">
        <p className="text-sm leading-relaxed text-neutral-600 dark:text-neutral-400">
          <strong>만 14세 미만은 가입할 수 없습니다.</strong> 서비스는 생년월일을
          받지 않으므로 나이를 확인할 수단이 없고, 가입 화면의 고지에 대한 이용자
          확인으로 갈음합니다. 만 14세 미만임이 확인되면 해당 계정과 관련 기록을
          지체 없이 삭제합니다.
        </p>
      </Section>

      <Section title="4. 보관과 파기">
        <List
          items={[
            "수집한 정보는 비공개 시험 운영 기간에만 보관합니다.",
            "시험이 끝나면 계정과 이용 기록을 모두 삭제합니다.",
            "이용자가 삭제를 요청하면 요청 즉시 해당 계정과 기록을 삭제합니다.",
          ]}
        />
        <p className="text-sm leading-relaxed text-neutral-600 dark:text-neutral-400">
          브라우저 저장소를 지우면 계정에 다시 접근할 수 없게 됩니다. 이 경우
          서버에 남은 기록의 삭제는 아래 문의처로 요청해 주세요.
        </p>
      </Section>

      <Section title="5. 처리 위탁과 국외 이전">
        <Table
          rows={[
            ["Supabase", "데이터베이스·인증. 데이터는 서울 리전에 저장됩니다"],
            ["Vercel", "웹사이트 호스팅"],
          ]}
        />
        <p className="text-sm leading-relaxed text-neutral-600 dark:text-neutral-400">
          두 회사 모두 국외 사업자입니다. 서비스 운영에 필요한 범위에서만 처리를
          위탁합니다.
        </p>
      </Section>

      <Section title="6. 이용자의 권리">
        <p className="text-sm leading-relaxed text-neutral-600 dark:text-neutral-400">
          자신의 정보에 대한 열람·정정·삭제·처리정지를 언제든 요청할 수 있습니다.
          닉네임과 소속은 앱에서 직접 바꿀 수 있고, 그 밖의 요청은 아래 문의처로
          연락해 주세요.
        </p>
      </Section>

      <Section title="7. 문의처">
        <p className="text-sm leading-relaxed text-neutral-600 dark:text-neutral-400">
          열람·삭제 요청을 비롯한 문의는 아래로 보내주세요.
        </p>
        <p className="rounded border border-neutral-200 px-4 py-3 font-mono text-sm dark:border-neutral-800">
          khm99629@gmail.com
        </p>
      </Section>

      <footer className="border-t border-neutral-200 pt-6 dark:border-neutral-800">
        <Link
          href="/"
          className="text-sm text-neutral-500 underline underline-offset-4"
        >
          서비스로 돌아가기
        </Link>
      </footer>
    </main>
  );
}

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="flex flex-col gap-3">
      <h2 className="font-medium">{title}</h2>
      {children}
    </section>
  );
}

function List({ items }: { items: string[] }) {
  return (
    <ul className="flex list-disc flex-col gap-1.5 pl-5 text-sm leading-relaxed text-neutral-600 dark:text-neutral-400">
      {items.map((t) => (
        <li key={t}>{t}</li>
      ))}
    </ul>
  );
}

function Table({ rows }: { rows: [string, string][] }) {
  return (
    <dl className="divide-y divide-neutral-200 rounded border border-neutral-200 text-sm dark:divide-neutral-800 dark:border-neutral-800">
      {rows.map(([term, desc]) => (
        <div key={term} className="flex flex-col gap-1 px-4 py-3 sm:flex-row sm:gap-4">
          <dt className="shrink-0 font-medium sm:w-32">{term}</dt>
          <dd className="text-neutral-600 dark:text-neutral-400">{desc}</dd>
        </div>
      ))}
    </dl>
  );
}
