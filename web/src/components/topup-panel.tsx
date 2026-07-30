"use client";

import { useCallback, useEffect, useState } from "react";
import {
  getTopupState,
  listProducts,
  nextOpenAt,
  purchase,
  PURCHASE_MESSAGE,
  type HeartProduct,
} from "@/lib/hearts";

/**
 * 하트 충전.
 *
 * ⚠️ 결제 화면이 아니다. 누르면 그 자리에서 하트가 들어온다.
 * 이용자가 오해하지 않도록 화면이 그 사실을 먼저 밝힌다 — 값이 적혀 있는데
 * 결제가 없으면 "왜 안 빠져나갔지"를 나중에 묻게 된다.
 */
export function TopupPanel({
  hearts,
  onClose,
  onChanged,
}: {
  hearts: number;
  onClose: () => void;
  onChanged: () => void;
}) {
  const [products, setProducts] = useState<HeartProduct[]>([]);
  const [canBuy, setCanBuy] = useState(true);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");

  const reload = useCallback(
    () =>
      Promise.all([listProducts(), getTopupState()])
        .then(([rows, state]) => {
          setProducts(rows);
          setCanBuy(state.canPurchase);
          setError("");
        })
        .catch((e) => setError(e instanceof Error ? e.message : String(e)))
        .finally(() => setLoading(false)),
    [],
  );

  useEffect(() => {
    reload();
  }, [reload]);

  async function buy(code: string) {
    setBusy(code);
    setNotice("");
    setError("");
    try {
      const result = await purchase(code);
      setNotice(PURCHASE_MESSAGE[result]);
      await reload();
      onChanged();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">하트 충전</h2>
        <button
          type="button"
          onClick={onClose}
          className="text-sm text-neutral-500 underline underline-offset-4"
        >
          홈으로
        </button>
      </div>

      <div className="rounded border border-neutral-300 px-4 py-3 dark:border-neutral-700">
        <p className="text-xs text-neutral-500">지금 하트</p>
        <p className="font-mono text-2xl font-semibold tabular-nums">
          {hearts.toLocaleString()}
        </p>
      </div>

      {/* 값이 적혀 있는데 결제가 없다. 먼저 밝히지 않으면 나중에 오해가 된다. */}
      <p className="rounded border border-dashed border-neutral-300 px-4 py-3 text-xs leading-relaxed text-neutral-600 dark:border-neutral-700 dark:text-neutral-400">
        <strong>시험판이라 실제 결제가 없습니다.</strong> 누르면 바로 충전돼요.
        가격은 나중에 붙일 실제 상품과 같게 적어둔 것입니다.
        <br />
        대신 <strong>하루에 한 번만</strong> 받을 수 있습니다.
      </p>

      {notice && (
        <p className="rounded border border-neutral-300 px-4 py-3 text-sm dark:border-neutral-700">
          {notice}
        </p>
      )}
      {error && (
        <p className="rounded border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-800 dark:border-red-900 dark:bg-red-950/40 dark:text-red-300">
          {error}
        </p>
      )}

      {loading && <p className="font-mono text-sm text-neutral-500">불러오는 중…</p>}

      {!loading && !canBuy && (
        <p className="rounded border border-neutral-300 px-4 py-4 text-center text-sm leading-relaxed text-neutral-600 dark:border-neutral-700 dark:text-neutral-400">
          오늘은 이미 충전했습니다.
          <br />
          <strong>{nextOpenAt()}</strong>에 다시 받을 수 있어요.
        </p>
      )}

      <ul className="flex flex-col gap-2">
        {products.map((p) => (
          <li key={p.code}>
            <button
              type="button"
              disabled={!canBuy || busy !== null}
              onClick={() => buy(p.code)}
              className="flex w-full items-center justify-between gap-3 rounded border border-neutral-300 px-4 py-4 text-left transition-opacity disabled:opacity-35 dark:border-neutral-700"
            >
              <span className="flex flex-col gap-0.5">
                <span className="font-mono text-lg font-semibold tabular-nums">
                  {p.hearts.toLocaleString()}
                  <span className="ml-1 text-xs font-normal text-neutral-500">하트</span>
                </span>
                {p.label && (
                  <span className="text-xs text-neutral-500">{p.label}</span>
                )}
              </span>
              <span className="shrink-0 font-mono text-sm tabular-nums text-neutral-600 dark:text-neutral-400">
                {busy === p.code ? "충전 중…" : `${p.price.toLocaleString()}원`}
              </span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
