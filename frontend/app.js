/* ============================================================
   CONFIGURATION
============================================================ */

const API_URL = "http://127.0.0.1:8000";


/* ============================================================
   ELEMENTS
============================================================ */

const form =
    document.getElementById("recoveryForm");

const recoverButton =
    document.getElementById("recoverButton");

const buttonText =
    document.getElementById("buttonText");

const buttonLoader =
    document.getElementById("buttonLoader");

const emptyState =
    document.getElementById("emptyState");

const resultContent =
    document.getElementById("resultContent");

const resultStatus =
    document.getElementById("resultStatus");


/* ============================================================
   SESSION DATA
============================================================ */

const transactions = [];

let errorCount = 0;


/* ============================================================
   FORM SUBMISSION
============================================================ */

form.addEventListener("submit", async (event) => {

    event.preventDefault();

    setLoading(true);

    try {

        const payment = {

            transaction_id:
                document
                    .getElementById("transaction_id")
                    .value
                    .trim(),

            amount:
                Number(
                    document.getElementById("amount").value
                ),

            payment_method:
                document.getElementById("payment_method").value,

            customer_type:
                document.getElementById("customer_type").value,

            failure_type:
                document.getElementById("failure_type").value,

            failure_code:
                document.getElementById("failure_code").value,

            attempt_count:
                Number(
                    document.getElementById("attempt_count").value
                ),

            previous_transactions:
                Number(
                    document
                        .getElementById("previous_transactions")
                        .value
                ),

            previous_success_rate:
                Number(
                    document
                        .getElementById("previous_success_rate")
                        .value
                ),

            customer_age_days: 240,

            time_since_failure_min: 10,

            hour_of_day: 14,

            is_weekend: 0
        };


        /* ----------------------------------------------------
           Basic frontend validation
        ---------------------------------------------------- */

        validatePayment(payment);


        /* ----------------------------------------------------
           API REQUEST
        ---------------------------------------------------- */

        const response = await fetch(
            `${API_URL}/api/v1/recover`,
            {
                method: "POST",

                headers: {
                    "Content-Type": "application/json",
                    "Accept": "application/json"
                },

                body: JSON.stringify(payment)
            }
        );


        let data;

        try {

            data = await response.json();

        } catch {

            throw new Error(
                "The recovery service returned an invalid response."
            );

        }


        if (!response.ok) {

            const message =
                data?.detail?.message ||
                data?.detail ||
                data?.message ||
                "Recovery request failed.";

            throw new Error(message);

        }


        if (!data.result) {

            throw new Error(
                "The API response did not contain a recovery result."
            );

        }


        displayResult(data.result);

        saveTransaction(data.result, payment);


    }

    catch (error) {

        console.error(
            "ReviveAI API Error:",
            error
        );

        errorCount++;

        showError(
            error.message ||
            "Unable to complete recovery."
        );

        updateAnalytics();

    }

    finally {

        setLoading(false);

    }

});


/* ============================================================
   VALIDATION
============================================================ */

function validatePayment(payment) {

    if (!payment.transaction_id) {

        throw new Error(
            "Transaction ID is required."
        );

    }


    if (
        !Number.isFinite(payment.amount) ||
        payment.amount <= 0
    ) {

        throw new Error(
            "Amount must be greater than zero."
        );

    }


    if (
        !Number.isInteger(payment.attempt_count) ||
        payment.attempt_count < 0
    ) {

        throw new Error(
            "Attempt count must be a valid non-negative number."
        );

    }


    if (
        !Number.isInteger(payment.previous_transactions) ||
        payment.previous_transactions < 0
    ) {

        throw new Error(
            "Previous transactions must be a valid non-negative number."
        );

    }


    if (
        !Number.isFinite(payment.previous_success_rate) ||
        payment.previous_success_rate < 0 ||
        payment.previous_success_rate > 1
    ) {

        throw new Error(
            "Previous success rate must be between 0 and 1."
        );

    }

}


/* ============================================================
   LOADING
============================================================ */

function setLoading(loading) {

    recoverButton.disabled = loading;

    buttonText.classList.toggle(
        "hidden",
        loading
    );

    buttonLoader.classList.toggle(
        "hidden",
        !loading
    );

}


/* ============================================================
   DISPLAY RESULT
============================================================ */

function displayResult(result) {

    emptyState.classList.add("hidden");

    resultContent.classList.remove("hidden");


    const risk =
        result.risk || {};

    const diagnosis =
        result.diagnosis || {};

    const policy =
        result.policy || {};

    const action =
        result.action || {};

    const verification =
        result.verification || {};


    /* ========================================================
       RISK
    ======================================================== */

    const probability =
        Number(
            risk.recovery_probability ?? 0
        );


    const safeProbability =
        Math.min(
            Math.max(probability, 0),
            1
        );


    document.getElementById(
        "recoveryProbability"
    ).textContent =
        `${(safeProbability * 100).toFixed(1)}%`;


    document.getElementById(
        "probabilityBar"
    ).style.width =
        `${safeProbability * 100}%`;


    document.getElementById(
        "riskLevel"
    ).textContent =
        risk.risk_level || "UNKNOWN";


    styleRiskLevel(
        risk.risk_level
    );


    /* ========================================================
       DIAGNOSIS
    ======================================================== */

    document.getElementById(
        "diagnosisCategory"
    ).textContent =
        diagnosis.diagnosis_category || "—";


    document.getElementById(
        "recoveryStrategy"
    ).textContent =
        diagnosis.recovery_strategy || "—";


    document.getElementById(
        "retryable"
    ).textContent =
        formatBoolean(
            diagnosis.retryable
        );


    document.getElementById(
        "automaticRecovery"
    ).textContent =
        formatBoolean(
            diagnosis.automatic_recovery
        );


    document.getElementById(
        "diagnosisReason"
    ).textContent =
        diagnosis.diagnosis_reason ||
        "No diagnosis explanation provided.";


    /* ========================================================
       POLICY
    ======================================================== */

    document.getElementById(
        "policyDecision"
    ).textContent =
        policy.decision || "—";


    document.getElementById(
        "policyReason"
    ).textContent =
        policy.reason || "—";


    stylePolicy(
        policy.decision
    );


    /* ========================================================
       ACTION
    ======================================================== */

    document.getElementById(
        "actionName"
    ).textContent =
        action.action || "—";


    document.getElementById(
        "actionExecuted"
    ).textContent =
        formatBoolean(
            action.executed
        );


    /* ========================================================
       VERIFICATION
    ======================================================== */

    const recovered =
        verification.recovered === true;


    document.getElementById(
        "verificationStatus"
    ).textContent =
        verification.verification_status ||
        "UNKNOWN";


    document.getElementById(
        "revenueRecovered"
    ).textContent =
        formatCurrency(
            verification.revenue_recovered
        );


    document.getElementById(
        "verificationReason"
    ).textContent =
        verification.reason ||
        "Verification completed.";


    /* ========================================================
       HERO
    ======================================================== */

    const recoveredAmount =
        Number(
            verification.revenue_recovered ?? 0
        );


    document.getElementById(
        "heroRevenue"
    ).textContent =
        formatCurrency(
            recoveredAmount
        );


    updateDecisionHero(
        result.status,
        recovered,
        recoveredAmount
    );


    /* ========================================================
       OVERALL STATUS
    ======================================================== */

    updateOverallStatus(
        result.status,
        recovered
    );


    updateAnalytics();

}


/* ============================================================
   HERO DECISION
============================================================ */

function updateDecisionHero(
    pipelineStatus,
    recovered,
    revenue
) {

    const title =
        document.getElementById(
            "decisionTitle"
        );

    const subtitle =
        document.getElementById(
            "decisionSubtitle"
        );

    const heroRevenue =
        document.getElementById(
            "heroRevenue"
        );


    heroRevenue.textContent =
        formatCurrency(revenue);


    if (recovered) {

        title.textContent =
            "Payment recovered";

        subtitle.textContent =
            "Recovery action executed and verified successfully.";

        return;
    }


    if (
        pipelineStatus === "not_recovered" ||
        pipelineStatus === "blocked"
    ) {

        title.textContent =
            "Recovery blocked";

        subtitle.textContent =
            "The payment was not automatically recovered.";

        heroRevenue.style.color =
            "#b77908";

        return;
    }


    title.textContent =
        "Recovery completed";

    subtitle.textContent =
        "The recovery pipeline completed without recovery.";

}


/* ============================================================
   OVERALL STATUS
============================================================ */

function updateOverallStatus(
    pipelineStatus,
    recovered
) {

    resultStatus.className =
        "status-badge";


    if (recovered) {

        resultStatus.textContent =
            "Recovered";

        resultStatus.classList.add(
            "success"
        );

        return;
    }


    if (
        pipelineStatus ===
        "not_recovered" ||
        pipelineStatus ===
        "blocked"
    ) {

        resultStatus.textContent =
            "Not Recovered";

        resultStatus.classList.add(
            "warning"
        );

        return;
    }


    resultStatus.textContent =
        pipelineStatus ||
        "Completed";

    resultStatus.classList.add(
        "neutral"
    );

}


/* ============================================================
   RISK STYLE
============================================================ */

function styleRiskLevel(level) {

    const element =
        document.getElementById(
            "riskLevel"
        );


    element.className =
        "risk-badge";


    const normalized =
        String(level || "")
            .toLowerCase();


    if (normalized === "low") {

        element.style.background =
            "#e9f8f2";

        element.style.color =
            "#159570";

    }

    else if (
        normalized === "medium"
    ) {

        element.style.background =
            "#fff6df";

        element.style.color =
            "#b77908";

    }

    else if (
        normalized === "high"
    ) {

        element.style.background =
            "#fff0f0";

        element.style.color =
            "#c84242";

    }

    else {

        element.style.background =
            "#eef1f4";

        element.style.color =
            "#667085";

    }

}


/* ============================================================
   POLICY STYLE
============================================================ */

function stylePolicy(decision) {

    const card =
        document.getElementById(
            "policyCard"
        );

    const icon =
        document.getElementById(
            "policyIcon"
        );


    const normalized =
        String(decision || "")
            .toLowerCase();


    if (
        normalized === "approved"
    ) {

        card.style.background =
            "#fbfdfc";

        card.style.borderColor =
            "#dcefe6";

        icon.textContent =
            "✓";

        icon.style.color =
            "#159570";

        return;
    }


    if (
        normalized === "blocked"
    ) {

        card.style.background =
            "#fffdf9";

        card.style.borderColor =
            "#f3e4c2";

        icon.textContent =
            "×";

        icon.style.color =
            "#b77908";

        return;
    }


    card.style.background =
        "#fbfcfd";

    card.style.borderColor =
        "#e5e9ef";

    icon.textContent =
        "•";

}


/* ============================================================
   ERROR DISPLAY
============================================================ */

function showError(message) {

    emptyState.classList.add("hidden");

    resultContent.classList.remove("hidden");


    resultStatus.className =
        "status-badge danger";

    resultStatus.textContent =
        "Error";


    document.getElementById(
        "decisionTitle"
    ).textContent =
        "Recovery unavailable";


    document.getElementById(
        "decisionSubtitle"
    ).textContent =
        "The request could not be completed safely.";


    document.getElementById(
        "heroRevenue"
    ).textContent =
        "₹0.00";


    document.getElementById(
        "heroRevenue"
    ).style.color =
        "#c84242";


    document.getElementById(
        "recoveryProbability"
    ).textContent =
        "—";


    document.getElementById(
        "probabilityBar"
    ).style.width =
        "0%";


    document.getElementById(
        "riskLevel"
    ).textContent =
        "—";


    document.getElementById(
        "diagnosisCategory"
    ).textContent =
        "API Error";


    document.getElementById(
        "recoveryStrategy"
    ).textContent =
        "—";


    document.getElementById(
        "retryable"
    ).textContent =
        "—";


    document.getElementById(
        "automaticRecovery"
    ).textContent =
        "—";


    document.getElementById(
        "diagnosisReason"
    ).textContent =
        message;


    document.getElementById(
        "policyDecision"
    ).textContent =
        "—";


    document.getElementById(
        "policyReason"
    ).textContent =
        "Request could not be completed.";


    document.getElementById(
        "actionName"
    ).textContent =
        "—";


    document.getElementById(
        "actionExecuted"
    ).textContent =
        "NO";


    document.getElementById(
        "verificationStatus"
    ).textContent =
        "SKIPPED";


    document.getElementById(
        "revenueRecovered"
    ).textContent =
        "₹0.00";


    document.getElementById(
        "verificationReason"
    ).textContent =
        "No recovery action was executed because the request failed.";

}


/* ============================================================
   TRANSACTION HISTORY
============================================================ */

function saveTransaction(
    result,
    payment
) {

    const verification =
        result.verification || {};

    const diagnosis =
        result.diagnosis || {};

    const action =
        result.action || {};


    const transaction = {

        transaction_id:
            result.transaction_id ||
            payment.transaction_id ||
            "UNKNOWN",

        amount:
            Number(
                verification.amount_at_risk ??
                payment.amount ??
                0
            ),

        failure:
            diagnosis.failure_code ||
            payment.failure_code ||
            diagnosis.diagnosis_category ||
            "—",

        action:
            action.action ||
            "—",

        status:
            verification.verification_status ||
            result.status ||
            "UNKNOWN",

        recovered:
            verification.recovered === true,

        revenue:
            Number(
                verification.revenue_recovered ??
                0
            )

    };


    transactions.unshift(
        transaction
    );


    updateTransactions();

    updateAnalytics();

}


/* ============================================================
   TRANSACTION TABLE
============================================================ */

function updateTransactions() {

    const tableBody =
        document.getElementById(
            "transactionTableBody"
        );


    const count =
        document.getElementById(
            "transactionCount"
        );


    if (!tableBody) {
        return;
    }


    if (count) {

        count.textContent =
            `${transactions.length} ${
                transactions.length === 1
                    ? "event"
                    : "events"
            }`;

    }


    if (transactions.length === 0) {

        tableBody.innerHTML = `
            <tr>
                <td colspan="5" class="empty-table">
                    No transactions yet.
                </td>
            </tr>
        `;

        return;
    }


    tableBody.innerHTML =
        transactions
            .map((transaction) => {

                const statusClass =
                    transaction.recovered
                        ? "success"
                        : (
                            transaction.status
                                .toLowerCase()
                                .includes("error")
                                ? "danger"
                                : "warning"
                        );


                return `
                    <tr>

                        <td>
                            <strong>
                                ${escapeHtml(
                                    transaction.transaction_id
                                )}
                            </strong>
                        </td>

                        <td>
                            ${formatCurrency(
                                transaction.amount
                            )}
                        </td>

                        <td>
                            ${escapeHtml(
                                transaction.failure
                            )}
                        </td>

                        <td>
                            ${escapeHtml(
                                transaction.action
                            )}
                        </td>

                        <td>

                            <span
                                class="table-status ${statusClass}"
                            >
                                ${escapeHtml(
                                    transaction.status
                                )}
                            </span>

                        </td>

                    </tr>
                `;

            })
            .join("");

}


/* ============================================================
   ANALYTICS
============================================================ */

function updateAnalytics() {

    const total =
        transactions.length;


    const recovered =
        transactions.filter(
            transaction =>
                transaction.recovered
        ).length;


    const blocked =
        transactions.filter(
            transaction =>
                !transaction.recovered &&
                !String(
                    transaction.status
                )
                    .toLowerCase()
                    .includes("error")
        ).length;


    const revenue =
        transactions.reduce(
            (sum, transaction) =>
                sum + transaction.revenue,
            0
        );


    const recoveryRate =
        total > 0
            ? (recovered / total) * 100
            : 0;


    setText(
        "totalTransactions",
        total
    );


    setText(
        "totalRecovered",
        recovered
    );


    setText(
        "recoveryRate",
        `${recoveryRate.toFixed(1)}%`
    );


    setText(
        "totalRevenue",
        formatCurrency(revenue)
    );


    setText(
        "analyticsRecovered",
        recovered
    );


    setText(
        "analyticsBlocked",
        blocked
    );


    setText(
        "analyticsErrors",
        errorCount
    );

}


/* ============================================================
   NAVIGATION
============================================================ */

const navItems =
    document.querySelectorAll(
        ".nav-item"
    );


const sections = {

    recovery:
        document.getElementById(
            "recoverySection"
        ),

    transactions:
        document.getElementById(
            "transactionsSection"
        ),

    analytics:
        document.getElementById(
            "analyticsSection"
        )

};


navItems.forEach((item) => {

    item.addEventListener(
        "click",
        () => {

            const section =
                item.dataset.section;


            navItems.forEach(
                nav =>
                    nav.classList.remove(
                        "active"
                    )
            );


            item.classList.add(
                "active"
            );


            Object.values(sections)
                .forEach(
                    element =>
                        element.classList.add(
                            "hidden"
                        )
                );


            if (
                sections[section]
            ) {

                sections[section]
                    .classList.remove(
                        "hidden"
                    );

            }


            if (
                section ===
                "transactions"
            ) {

                updateTransactions();

            }


            if (
                section ===
                "analytics"
            ) {

                updateAnalytics();

            }

        }
    );

});


/* ============================================================
   HELPERS
============================================================ */

function setText(
    id,
    value
) {

    const element =
        document.getElementById(id);


    if (element) {

        element.textContent =
            value;

    }

}


function formatBoolean(value) {

    if (value === true) {

        return "YES";

    }


    if (value === false) {

        return "NO";

    }


    return "—";

}


function formatCurrency(value) {

    const amount =
        Number(value ?? 0);


    return new Intl.NumberFormat(
        "en-IN",
        {
            style: "currency",
            currency: "INR",
            maximumFractionDigits: 2
        }
    ).format(amount);

}


function escapeHtml(value) {

    return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");

}


/* ============================================================
   INITIAL STATE
============================================================ */

updateTransactions();

updateAnalytics();