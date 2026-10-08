"use strict";


const state = {
    status: null,
    overview: null,
    telemetry: null,
    history: [],
    sdr: null,

    mission: {
        events: [],
        total: 0,
        statistics: {
            events: 0,
            missions: 0,
            satellites: 0,
            errors: 0,
            warnings: 0
        },
        available: false
    },

    interactionMode: true,

    missionFilters: {
        search: "",
        severity: "",
        eventType: ""
    },

    selectedEvent: null,
    selectedHistory: null,

    refreshBusy: false
};


const $ = (id) =>
    document.getElementById(id);


function escapeHtml(value) {
    return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}


function formatNumber(value) {
    if (
        value === null ||
        value === undefined ||
        value === ""
    ) {
        return "—";
    }

    const number = Number(value);

    if (!Number.isFinite(number)) {
        return escapeHtml(value);
    }

    return number.toLocaleString(
        undefined,
        {
            maximumFractionDigits: 3
        }
    );
}


function formatTime(value) {
    if (!value) {
        return "—";
    }

    const date = new Date(value);

    if (
        Number.isNaN(
            date.getTime()
        )
    ) {
        return String(value);
    }

    return date.toLocaleTimeString(
        [],
        {
            hour: "2-digit",
            minute: "2-digit",
            second: "2-digit"
        }
    );
}


function formatDateTime(value) {
    if (!value) {
        return "—";
    }

    const date = new Date(value);

    if (
        Number.isNaN(
            date.getTime()
        )
    ) {
        return String(value);
    }

    return date.toLocaleString(
        [],
        {
            year: "numeric",
            month: "short",
            day: "2-digit",
            hour: "2-digit",
            minute: "2-digit",
            second: "2-digit"
        }
    );
}


function formatUtcClock() {
    const now = new Date();

    return now.toLocaleTimeString(
        "en-GB",
        {
            timeZone: "UTC",
            hour12: false
        }
    );
}


function eventSeverityClass(
    severity
) {
    const value =
        String(
            severity || "INFO"
        ).toLowerCase();

    return [
        "info",
        "success",
        "warning",
        "error"
    ].includes(value)
        ? value
        : "info";
}


function isReplayData(record) {
    if (!record) {
        return false;
    }

    const source =
        String(
            record.source || ""
        ).toLowerCase();

    const mode =
        String(
            record.metadata?.mode || ""
        ).toUpperCase();

    return (
        source === "replay" ||
        mode === "REPLAY"
    );
}


function dataModeLabel(record) {
    if (isReplayData(record)) {
        return "REPLAY / DEVELOPMENT";
    }

    if (record) {
        return String(
            record.source ||
            "UNKNOWN"
        ).toUpperCase();
    }

    return "STANDBY";
}


function openDetail(
    title,
    html
) {
    if (!state.interactionMode) {
        return;
    }

    $("detailTitle").textContent =
        title;

    $("detailBody").innerHTML =
        html;

    $("detailOverlay").classList.add(
        "open"
    );

    $("detailOverlay").setAttribute(
        "aria-hidden",
        "false"
    );

    document.body.classList.add(
        "drawer-open"
    );
}


function closeDetail() {
    $("detailOverlay").classList.remove(
        "open"
    );

    $("detailOverlay").setAttribute(
        "aria-hidden",
        "true"
    );

    document.body.classList.remove(
        "drawer-open"
    );
}


function detailRow(
    label,
    value
) {
    return `
        <div class="detail-row">
            <span>${escapeHtml(label)}</span>
            <strong>${escapeHtml(
                value ?? "—"
            )}</strong>
        </div>
    `;
}


function addLocalEvent(
    message,
    type = "info"
) {
    /*
     * Local UI notices are deliberately not represented as
     * mission events. Only persisted Mission Log events are
     * shown in the operational Mission Log.
     */
    console.debug(
        `[OrbitWatch:${type}] ${message}`
    );
}


function renderSystemStatus() {
    const data = state.status;

    if (!data) {
        return;
    }

    const status =
        String(
            data.status || "unknown"
        ).toLowerCase();

    $("systemStatus").textContent =
        status === "online"
            ? "ONLINE"
            : status.toUpperCase();

    $("systemDot").classList.toggle(
        "online",
        status === "online"
    );

    $("systemDot").classList.toggle(
        "offline",
        status !== "online"
    );

    $("operatingMode").textContent =
        data.mode || "STANDBY";

    $("modeDescription").textContent =
        data.mode === "REPLAY"
            ? "Controlled replay/development telemetry available"
            : "Awaiting telemetry reception";

    $("footerStatus").textContent =
        status === "online"
            ? "MISSION CONTROL ONLINE"
            : "SYSTEM DEGRADED";

    const missionAvailable =
        data.mission_log?.available;

    $("missionLogStatus").textContent =
        missionAvailable
            ? "LIVE"
            : "NO DATABASE";
}


function renderOverview() {
    const data = state.overview;

    if (!data) {
        return;
    }

    const packetCount =
        Number(
            data.statistics?.packet_count ?? 0
        );

    const satelliteCount =
        Number(
            data.statistics?.satellite_count ?? 0
        );

    $("packetCount").textContent =
        formatNumber(packetCount);

    $("satelliteCount").textContent =
        formatNumber(satelliteCount);

    const satellite =
        data.satellite ||
        "NO CONTACT";

    $("activeSatellite").textContent =
        String(
            satellite
        ).toUpperCase();

    $("orbitSatellite").textContent =
        satellite || "—";

    const latest =
        data.last_packet;

    if (!latest) {

        $("lastContact").textContent =
            "—";

        $("dataSource").textContent =
            "—";

        $("telemetryState").textContent =
            "WAITING";

        $("trackingStatus").textContent =
            "NO TRACK";

        $("telemetryStatus").textContent =
            "NO DATA";

        $("decoderState").textContent =
            "READY";

        return;
    }

    const source =
        String(
            latest.source ||
            "UNKNOWN"
        ).toUpperCase();

    const metadata =
        latest.metadata || {};

    const replayMode =
        source === "REPLAY" ||
        source === "DEVELOPMENT" ||
        String(
            metadata.mode || ""
        ).toUpperCase() === "REPLAY" ||
        String(
            metadata.mode || ""
        ).toUpperCase() === "DEVELOPMENT" ||
        metadata.replay === true ||
        metadata.development === true;

    const valid =
        latest.valid !== false;

    $("lastContact").textContent =
        formatTime(
            latest.timestamp
        );

    $("dataSource").textContent =
        replayMode
            ? "REPLAY"
            : source;

    if (replayMode) {

        /*
         * Replay data is real persisted application data, but it must
         * never be presented as live RF contact.
         */
        $("telemetryState").textContent =
            valid
                ? "REPLAY"
                : "INVALID";

        $("trackingStatus").textContent =
            "REPLAY";

        $("telemetryStatus").textContent =
            valid
                ? "REPLAY"
                : "INVALID";

        $("decoderState").textContent =
            valid
                ? "ACTIVE"
                : "CHECK";

        return;
    }

    $("telemetryState").textContent =
        valid
            ? "ACTIVE"
            : "INVALID";

    $("trackingStatus").textContent =
        "TRACKING";

    $("telemetryStatus").textContent =
        valid
            ? "LIVE"
            : "INVALID";

    $("decoderState").textContent =
        valid
            ? "ACTIVE"
            : "CHECK";
}


function renderTelemetry() {
    const container =
        $("telemetryValues");

    const empty =
        $("telemetryEmpty");

    if (!container || !empty) {
        return;
    }

    const values =
        state.overview?.telemetry || [];

    if (!values.length) {

        container.innerHTML = "";

        empty.style.display =
            "flex";

        return;
    }

    empty.style.display =
        "none";

    container.innerHTML =
        values
            .map(
                (item, index) => `
                    <div
                        class="telemetry-value interactive-card"
                        tabindex="0"
                        data-telemetry-index="${index}"
                    >

                        <span>
                            ${escapeHtml(
                                String(
                                    item.name ||
                                    "UNKNOWN"
                                )
                                    .replaceAll(
                                        "_",
                                        " "
                                    )
                                    .toUpperCase()
                            )}
                        </span>

                        <strong>
                            ${escapeHtml(
                                formatNumber(
                                    item.value
                                )
                            )}
                        </strong>

                        ${
                            item.unit
                                ? `
                                    <small>
                                        ${escapeHtml(
                                            item.unit
                                        )}
                                    </small>
                                `
                                : ""
                        }

                    </div>
                `
            )
            .join("");

    container
        .querySelectorAll(
            "[data-telemetry-index]"
        )
        .forEach(card => {

            const index =
                Number(
                    card.dataset
                        .telemetryIndex
                );

            const activate =
                () => {

                    const item =
                        values[index];

                    if (!item) {
                        return;
                    }

                    openDetail(
                        "Telemetry Value",
                        `
                            ${detailRow(
                                "FIELD",
                                item.name
                            )}

                            ${detailRow(
                                "VALUE",
                                formatNumber(
                                    item.value
                                )
                            )}

                            ${detailRow(
                                "UNIT",
                                item.unit ||
                                "—"
                            )}

                            ${detailRow(
                                "DATA TYPE",
                                item.data_type ||
                                "—"
                            )}

                            ${detailRow(
                                "SATELLITE",
                                state.overview?.satellite ||
                                "—"
                            )}

                            ${detailRow(
                                "SOURCE",
                                dataModeLabel(
                                    state.overview
                                        ?.last_packet
                                )
                            )}

                            ${detailRow(
                                "LAST UPDATE",
                                formatDateTime(
                                    state.overview
                                        ?.last_packet
                                        ?.timestamp
                                )
                            )}
                        `
                    );
                };

            card.addEventListener(
                "click",
                activate
            );

            card.addEventListener(
                "keydown",
                event => {

                    if (
                        event.key === "Enter" ||
                        event.key === " "
                    ) {
                        event.preventDefault();
                        activate();
                    }
                }
            );
        });
}


function renderPackets() {
    const latest =
        state.overview?.last_packet;

    const total =
        Number(
            state.overview
                ?.statistics
                ?.packet_count || 0
        );

    $("packetTotal").textContent =
        formatNumber(total);

    let valid = 0;
    let crc = 0;
    let invalid = 0;

    for (
        const record
        of state.history
    ) {

        if (
            record.valid === false
        ) {
            invalid += 1;
        } else {
            valid += 1;
        }

        if (
            record.crc_ok === true
        ) {
            crc += 1;
        }
    }

    /*
     * The latest packet is usually included
     * in history. Avoid double-counting it.
     */
    if (
        latest &&
        !state.history.some(
            record =>
                record.packet_id &&
                latest.packet_id &&
                record.packet_id ===
                    latest.packet_id
        )
    ) {

        if (
            latest.valid === false
        ) {
            invalid += 1;
        } else {
            valid += 1;
        }

        if (
            latest.crc_ok === true
        ) {
            crc += 1;
        }
    }

    $("validPackets").textContent =
        formatNumber(valid);

    $("crcPackets").textContent =
        formatNumber(crc);

    $("invalidPackets").textContent =
        formatNumber(invalid);

    const denominator =
        valid + invalid;

    $("packetValidBar").style.width =
        denominator > 0
            ? `${Math.round(
                (valid / denominator) *
                100
            )}%`
            : "0%";
}


function renderHistory() {
    const container =
        $("historyChart");

    if (!container) {
        return;
    }

    if (!state.history.length) {

        container.innerHTML = `
            <div class="history-empty">
                <div>◒</div>

                <strong>
                    NO HISTORICAL TELEMETRY
                </strong>

                <span>
                    Telemetry records will appear here after
                    successful decoding.
                </span>
            </div>
        `;

        return;
    }

    const numericPoints = [];

    for (
        const record
        of state.history
    ) {

        const values =
            record.values || {};

        for (
            const [name, item]
            of Object.entries(values)
        ) {

            const value =
                typeof item === "object"
                    ? item.value
                    : item;

            const number =
                Number(value);

            if (
                Number.isFinite(number)
            ) {

                numericPoints.push(
                    {
                        name,
                        value: number,
                        timestamp:
                            record.timestamp,
                        record
                    }
                );

                break;
            }
        }
    }

    if (!numericPoints.length) {

        container.innerHTML = `
            <div class="history-empty">
                <div>◒</div>

                <strong>
                    TELEMETRY RECEIVED
                </strong>

                <span>
                    Historical records contain no plottable
                    numeric values yet.
                </span>
            </div>
        `;

        return;
    }

    const width = 1000;
    const height = 160;
    const padding = 15;

    const values =
        numericPoints.map(
            point => point.value
        );

    const min =
        Math.min(...values);

    const max =
        Math.max(...values);

    const range =
        max - min || 1;

    const points =
        numericPoints
            .map(
                (point, index) => {

                    const x =
                        padding +
                        (
                            index /
                            Math.max(
                                numericPoints.length - 1,
                                1
                            )
                        ) *
                        (
                            width -
                            padding * 2
                        );

                    const y =
                        height -
                        padding -
                        (
                            (
                                point.value -
                                min
                            ) /
                            range
                        ) *
                        (
                            height -
                            padding * 2
                        );

                    return `${x.toFixed(
                        1
                    )},${y.toFixed(1)}`;
                }
            )
            .join(" ");

    container.innerHTML = `
        <svg
            viewBox="0 0 ${width} ${height}"
            preserveAspectRatio="none"
            style="
                width:100%;
                height:100%;
                overflow:visible;
            "
        >

            <polyline
                points="${points}"
                fill="none"
                stroke="var(--cyan)"
                stroke-width="2"
                vector-effect="non-scaling-stroke"
            />

        </svg>

        <div class="history-axis-label">
            ${escapeHtml(
                numericPoints[0].name
            )}
        </div>

        <div class="history-record-count">
            ${numericPoints.length}
            RECORDS
        </div>

        <div class="history-point-layer">
            ${numericPoints
                .map(
                    (point, index) => `
                        <button
                            class="history-point"
                            style="
                                left:${
                                    (
                                        padding +
                                        (
                                            index /
                                            Math.max(
                                                numericPoints.length - 1,
                                                1
                                            )
                                        ) *
                                        (
                                            width -
                                            padding * 2
                                        )
                                    ) /
                                    width *
                                    100
                                }%;
                            "
                            data-history-index="${index}"
                            title="${escapeHtml(
                                formatNumber(
                                    point.value
                                )
                            )}"
                        ></button>
                    `
                )
                .join("")}
        </div>
    `;

    const pointsLayer =
        container.querySelector(
            ".history-point-layer"
        );

    if (pointsLayer) {

        pointsLayer
            .querySelectorAll(
                "[data-history-index]"
            )
            .forEach(button => {

                const index =
                    Number(
                        button.dataset
                            .historyIndex
                    );

                const point =
                    numericPoints[index];

                button.addEventListener(
                    "click",
                    () => {

                        if (!point) {
                            return;
                        }

                        const record =
                            point.record;

                        openDetail(
                            "Telemetry Record",
                            `
                                ${detailRow(
                                    "FIELD",
                                    point.name
                                )}

                                ${detailRow(
                                    "VALUE",
                                    formatNumber(
                                        point.value
                                    )
                                )}

                                ${detailRow(
                                    "TIMESTAMP",
                                    formatDateTime(
                                        record.timestamp
                                    )
                                )}

                                ${detailRow(
                                    "SATELLITE",
                                    record.satellite ||
                                    "—"
                                )}

                                ${detailRow(
                                    "PACKET ID",
                                    record.packet_id ||
                                    "—"
                                )}

                                ${detailRow(
                                    "SOURCE",
                                    dataModeLabel(
                                        record
                                    )
                                )}

                                ${detailRow(
                                    "VALID",
                                    record.valid === false
                                        ? "NO"
                                        : "YES"
                                )}

                                ${detailRow(
                                    "CRC",
                                    record.crc_ok === true
                                        ? "OK"
                                        : record.crc_ok === false
                                            ? "ERROR"
                                            : "NOT REPORTED"
                                )}
                            `
                        );
                    }
                );
            });
    }
}


function renderSdr() {
    const data =
        state.sdr;

    if (!data) {
        return;
    }

    const receiver =
        data.receiver || {};

    const stateName =
        receiver.state ||
        "UNAVAILABLE";

    $("receiverState").textContent =
        String(
            stateName
        ).toUpperCase();

    $("receiverStatus").textContent =
        receiver.available
            ? "AVAILABLE"
            : "OFFLINE";

    $("receiverDevices").textContent =
        formatNumber(
            Array.isArray(
                data.devices
            )
                ? data.devices.length
                : 0
        );

    const signal =
        receiver.signal_level ??
        receiver.signal_db ??
        receiver.power_db;

    if (
        Number.isFinite(
            Number(signal)
        )
    ) {

        const value =
            Number(signal);

        $("signalLevel").textContent =
            `${value.toFixed(1)} dB`;

        const percentage =
            Math.max(
                0,
                Math.min(
                    100,
                    (
                        (
                            value + 100
                        ) / 100
                    ) * 100
                )
            );

        $("signalMeter").style.width =
            `${percentage}%`;

    } else {

        $("signalLevel").textContent =
            "NO SIGNAL";

        $("signalMeter").style.width =
            "0%";
    }
}


function renderMissionStatistics() {
    const statistics =
        state.mission.statistics ||
        {};

    $("missionEventCount").textContent =
        formatNumber(
            statistics.events || 0
        );

    $("missionCount").textContent =
        formatNumber(
            statistics.missions || 0
        );

    $("missionErrorCount").textContent =
        formatNumber(
            statistics.errors || 0
        );

    $("missionWarningCount").textContent =
        formatNumber(
            statistics.warnings || 0
        );
}


function renderMissionEvents() {
    const container =
        $("eventLog");

    if (!container) {
        return;
    }

    const events =
        state.mission.events || [];

    if (!events.length) {

        container.innerHTML = `
            <div class="mission-empty">
                <span>◌</span>

                <strong>
                    NO MATCHING MISSION EVENTS
                </strong>

                <small>
                    Mission activity will appear here
                    when persisted by the mission logger.
                </small>
            </div>
        `;

        return;
    }

    container.innerHTML =
        events
            .map(
                (event, index) => {

                    const severity =
                        eventSeverityClass(
                            event.severity
                        );

                    return `
                        <button
                            class="
                                event
                                event-interactive
                                severity-${severity}
                            "
                            type="button"
                            data-event-index="${index}"
                        >

                            <span class="event-time">
                                ${escapeHtml(
                                    formatTime(
                                        event.timestamp
                                    )
                                )}
                            </span>

                            <span class="event-dot"></span>

                            <span class="event-content">

                                <span class="event-message">
                                    ${escapeHtml(
                                        event.message ||
                                        event.event_type ||
                                        "Mission event"
                                    )}
                                </span>

                                <span class="event-meta">
                                    ${escapeHtml(
                                        event.event_type ||
                                        "CUSTOM"
                                    )}
                                    •
                                    ${escapeHtml(
                                        event.severity ||
                                        "INFO"
                                    )}
                                </span>

                            </span>

                            <span class="event-open">
                                ›
                            </span>

                        </button>
                    `;
                }
            )
            .join("");

    container
        .querySelectorAll(
            "[data-event-index]"
        )
        .forEach(button => {

            const index =
                Number(
                    button.dataset
                        .eventIndex
                );

            button.addEventListener(
                "click",
                () => {

                    const event =
                        state.mission
                            .events[index];

                    if (!event) {
                        return;
                    }

                    state.selectedEvent =
                        event;

                    openDetail(
                        "Mission Event",
                        `
                            <div class="
                                detail-event-badge
                                severity-${eventSeverityClass(
                                    event.severity
                                )}
                            ">
                                ${escapeHtml(
                                    event.severity ||
                                    "INFO"
                                )}
                            </div>

                            ${detailRow(
                                "EVENT",
                                event.event_type
                            )}

                            ${detailRow(
                                "MESSAGE",
                                event.message
                            )}

                            ${detailRow(
                                "TIMESTAMP",
                                formatDateTime(
                                    event.timestamp
                                )
                            )}

                            ${detailRow(
                                "MISSION",
                                event.mission_id
                            )}

                            ${detailRow(
                                "SATELLITE",
                                event.satellite
                            )}

                            ${detailRow(
                                "PACKET ID",
                                event.packet_id
                            )}

                            ${detailRow(
                                "RECORDING",
                                event.recording_id
                            )}

                            <div class="detail-json">
                                <span>PAYLOAD</span>
                                <pre>${escapeHtml(
                                    JSON.stringify(
                                        event.payload || {},
                                        null,
                                        2
                                    )
                                )}</pre>
                            </div>
                        `
                    );
                }
            );
        });
}


function renderMissionTypes(
    types
) {
    const select =
        $("missionEventType");

    if (!select) {
        return;
    }

    const current =
        state.missionFilters
            .eventType;

    const values =
        Array.isArray(types)
            ? types
            : [];

    select.innerHTML = `
        <option value="">
            ALL EVENTS
        </option>

        ${values
            .map(
                type => `
                    <option value="${escapeHtml(
                        type
                    )}">
                        ${escapeHtml(
                            type
                        )}
                    </option>
                `
            )
            .join("")}
    `;

    select.value =
        current;
}


async function fetchJson(
    url
) {
    const response =
        await fetch(
            url,
            {
                headers: {
                    "Accept":
                        "application/json"
                },
                cache: "no-store"
            }
        );

    if (!response.ok) {
        throw new Error(
            `${url} returned HTTP ${response.status}`
        );
    }

    return response.json();
}


async function refreshStatus() {
    try {

        state.status =
            await fetchJson(
                "/api/status"
            );

        renderSystemStatus();

    } catch (error) {

        $("systemStatus").textContent =
            "OFFLINE";

        $("systemDot")
            .classList.remove(
                "online"
            );

        $("systemDot")
            .classList.add(
                "offline"
            );

        addLocalEvent(
            "Mission control API unavailable.",
            "error"
        );
    }
}


async function refreshOverview() {
    try {

        state.overview =
            await fetchJson(
                "/api/overview"
            );

        renderOverview();
        renderTelemetry();
        renderPackets();

    } catch (error) {

        addLocalEvent(
            "Telemetry overview unavailable.",
            "error"
        );
    }
}


async function refreshHistory() {
    try {

        const data =
            await fetchJson(
                "/api/telemetry/history?limit=50"
            );

        state.history =
            Array.isArray(
                data.history
            )
                ? data.history
                : [];

        renderHistory();
        renderPackets();

    } catch (error) {

        state.history = [];

        renderHistory();
    }
}


async function refreshSdr() {
    try {

        state.sdr =
            await fetchJson(
                "/api/sdr"
            );

        renderSdr();

    } catch (error) {

        $("receiverStatus").textContent =
            "OFFLINE";
    }
}


function buildMissionLogUrl() {
    const params =
        new URLSearchParams();

    params.set(
        "limit",
        "100"
    );

    const filters =
        state.missionFilters;

    if (filters.search) {
        params.set(
            "search",
            filters.search
        );
    }

    if (filters.severity) {
        params.set(
            "severity",
            filters.severity
        );
    }

    if (filters.eventType) {
        params.set(
            "event_type",
            filters.eventType
        );
    }

    return `/api/mission-log?${params.toString()}`;
}


async function refreshMissionLog() {
    try {

        const data =
            await fetchJson(
                buildMissionLogUrl()
            );

        state.mission = {
            events:
                Array.isArray(
                    data.events
                )
                    ? data.events
                    : [],

            total:
                Number(
                    data.total || 0
                ),

            statistics:
                data.statistics || {
                    events: 0,
                    missions: 0,
                    satellites: 0,
                    errors: 0,
                    warnings: 0
                },

            available:
                Boolean(
                    data.available
                )
        };

        renderMissionStatistics();
        renderMissionEvents();

        $("missionLogStatus").textContent =
            data.available
                ? "LIVE"
                : "NO DATABASE";

    } catch (error) {

        state.mission = {
            events: [],
            total: 0,
            statistics: {
                events: 0,
                missions: 0,
                satellites: 0,
                errors: 0,
                warnings: 0
            },
            available: false
        };

        renderMissionStatistics();
        renderMissionEvents();

        $("missionLogStatus").textContent =
            "ERROR";
    }
}


async function refreshMissionTypes() {
    try {

        const data =
            await fetchJson(
                "/api/mission-log/types"
            );

        renderMissionTypes(
            data.types || []
        );

    } catch (error) {
        console.debug(
            "Mission event types unavailable."
        );
    }
}


async function refreshAll() {
    if (state.refreshBusy) {
        return;
    }

    state.refreshBusy = true;

    try {

        await Promise.all([
            refreshStatus(),
            refreshOverview(),
            refreshHistory(),
            refreshSdr(),
            refreshMissionLog()
        ]);

    } finally {

        state.refreshBusy = false;
    }
}


function startClock() {
    const update =
        () => {

            $("utcClock").textContent =
                formatUtcClock();
        };

    update();

    setInterval(
        update,
        1000
    );
}


function startPolling() {
    setInterval(
        refreshAll,
        5000
    );
}


function toggleInteractionMode() {
    state.interactionMode =
        !state.interactionMode;

    const button =
        $("interactionMode");

    button.classList.toggle(
        "active",
        state.interactionMode
    );

    button.querySelector(
        ".interaction-led"
    ).style.opacity =
        state.interactionMode
            ? "1"
            : ".35";

    button.lastChild.textContent =
        state.interactionMode
            ? " ACTIVE"
            : " PASSIVE";

    document.body.classList.toggle(
        "interaction-disabled",
        !state.interactionMode
    );

    if (
        !state.interactionMode
    ) {
        closeDetail();
    }
}


function setupInteractionMode() {
    $("interactionMode")
        .addEventListener(
            "click",
            toggleInteractionMode
        );
}


function setupDetailDrawer() {
    $("detailClose")
        .addEventListener(
            "click",
            closeDetail
        );

    $("detailOverlay")
        .addEventListener(
            "click",
            event => {

                if (
                    event.target ===
                    $("detailOverlay")
                ) {
                    closeDetail();
                }
            }
        );

    document.addEventListener(
        "keydown",
        event => {

            if (
                event.key === "Escape"
            ) {
                closeDetail();
            }
        }
    );
}


function setupMetricInteractions() {
    document
        .querySelectorAll(
            "[data-detail]"
        )
        .forEach(card => {

            const activate =
                () => {

                    const type =
                        card.dataset
                            .detail;

                    if (
                        type ===
                        "active-satellite"
                    ) {

                        const latest =
                            state.overview
                                ?.last_packet;

                        openDetail(
                            "Active Satellite",
                            `
                                ${detailRow(
                                    "SATELLITE",
                                    state.overview
                                        ?.satellite ||
                                    "NO CONTACT"
                                )}

                                ${detailRow(
                                    "MODE",
                                    latest
                                        ? dataModeLabel(
                                            latest
                                        )
                                        : "STANDBY"
                                )}

                                ${detailRow(
                                    "TRACKING",
                                    latest
                                        ? (
                                            isReplayData(
                                                latest
                                            )
                                                ? "REPLAY DATA"
                                                : "ACTIVE"
                                        )
                                        : "NO CONTACT"
                                )}

                                ${detailRow(
                                    "LAST RECORD",
                                    formatDateTime(
                                        latest
                                            ?.timestamp
                                    )
                                )}

                                ${detailRow(
                                    "SOURCE",
                                    latest
                                        ?.source ||
                                    "—"
                                )}
                            `
                        );

                    } else if (
                        type ===
                        "packet-summary"
                    ) {

                        openDetail(
                            "Packet Summary",
                            `
                                ${detailRow(
                                    "TOTAL",
                                    state.overview
                                        ?.statistics
                                        ?.packet_count ||
                                    0
                                )}

                                ${detailRow(
                                    "VALID",
                                    $("validPackets")
                                        .textContent
                                )}

                                ${detailRow(
                                    "CRC OK",
                                    $("crcPackets")
                                        .textContent
                                )}

                                ${detailRow(
                                    "INVALID",
                                    $("invalidPackets")
                                        .textContent
                                )}
                            `
                        );

                    } else if (
                        type ===
                        "satellite-summary"
                    ) {

                        const satellites =
                            state.overview
                                ?.statistics
                                ?.satellite_count ||
                            0;

                        openDetail(
                            "Satellite Summary",
                            `
                                ${detailRow(
                                    "SATELLITES SEEN",
                                    satellites
                                )}

                                <div class="detail-list">
                                    ${
                                        (
                                            state.status
                                                ?.database
                                                ?.satellites ||
                                            []
                                        )
                                            .map(
                                                satellite => `
                                                    <span>
                                                        ${escapeHtml(
                                                            satellite
                                                        )}
                                                    </span>
                                                `
                                            )
                                            .join("")
                                    }
                                </div>
                            `
                        );

                    } else if (
                        type ===
                        "telemetry-summary"
                    ) {

                        const latest =
                            state.overview
                                ?.last_packet;

                        openDetail(
                            "Telemetry State",
                            `
                                ${detailRow(
                                    "STATE",
                                    latest?.valid === false
                                        ? "INVALID"
                                        : latest
                                            ? (
                                                isReplayData(
                                                    latest
                                                )
                                                    ? "REPLAY"
                                                    : "ACTIVE"
                                            )
                                            : "WAITING"
                                )}

                                ${detailRow(
                                    "FIELDS",
                                    state.overview
                                        ?.telemetry
                                        ?.length ||
                                    0
                                )}

                                ${detailRow(
                                    "LAST PACKET",
                                    latest
                                        ?.packet_id ||
                                    "—"
                                )}

                                ${detailRow(
                                    "SOURCE",
                                    latest
                                        ? dataModeLabel(
                                            latest
                                        )
                                        : "—"
                                )}
                            `
                        );
                    }
                };

            card.addEventListener(
                "click",
                activate
            );

            card.addEventListener(
                "keydown",
                event => {

                    if (
                        event.key === "Enter" ||
                        event.key === " "
                    ) {

                        event.preventDefault();

                        activate();
                    }
                }
            );
        });
}


function setupOrbitInteraction() {
    $("orbitScene")
        .addEventListener(
            "click",
            () => {

                const latest =
                    state.overview
                        ?.last_packet;

                openDetail(
                    "Orbital Situation",
                    `
                        ${detailRow(
                            "SATELLITE",
                            state.overview
                                ?.satellite ||
                            "NO CONTACT"
                        )}

                        ${detailRow(
                            "TRACK STATUS",
                            latest
                                ? (
                                    isReplayData(
                                        latest
                                    )
                                        ? "REPLAY DATA"
                                        : "TRACKING"
                                )
                                : "NO TRACK"
                        )}

                        ${detailRow(
                            "LAST RECORD",
                            formatDateTime(
                                latest
                                    ?.timestamp
                            )
                        )}

                        ${detailRow(
                            "DATA SOURCE",
                            latest
                                ? dataModeLabel(
                                    latest
                                )
                                : "—"
                        )}
                    `
                );
            }
        );
}


function setupPipelineInteraction() {
    document
        .querySelectorAll(
            "[data-pipeline]"
        )
        .forEach(node => {

            const activate =
                () => {

                    const stage =
                        node.dataset
                            .pipeline;

                    const descriptions = {
                        SDR:
                            "Software-defined radio subsystem. Receives IQ samples from the configured RF source.",
                        DSP:
                            "Digital signal processing stage. Filters and prepares received samples.",
                        DEMOD:
                            "Demodulation stage. Converts the processed signal into recoverable symbols.",
                        PACKET:
                            "Packet decoding stage. Handles protocols such as AX.25 and KISS.",
                        TELEM:
                            "Telemetry engine. Parses, validates, stores and exposes decoded telemetry."
                    };

                    openDetail(
                        `${stage} Pipeline Stage`,
                        `
                            ${detailRow(
                                "STAGE",
                                stage
                            )}

                            <div class="detail-description">
                                ${escapeHtml(
                                    descriptions[
                                        stage
                                    ] ||
                                    "Ground station pipeline stage."
                                )}
                            </div>
                        `
                    );
                };

            node.addEventListener(
                "click",
                activate
            );

            node.addEventListener(
                "keydown",
                event => {

                    if (
                        event.key === "Enter" ||
                        event.key === " "
                    ) {

                        event.preventDefault();

                        activate();
                    }
                }
            );
        });
}


function setupMissionControls() {
    const search =
        $("missionSearch");

    const severity =
        $("missionSeverity");

    const eventType =
        $("missionEventType");

    let searchTimer = null;

    search.addEventListener(
        "input",
        () => {

            clearTimeout(
                searchTimer
            );

            state.missionFilters
                .search =
                search.value.trim();

            searchTimer =
                setTimeout(
                    refreshMissionLog,
                    300
                );
        }
    );

    severity.addEventListener(
        "change",
        () => {

            state.missionFilters
                .severity =
                severity.value;

            refreshMissionLog();
        }
    );

    eventType.addEventListener(
        "change",
        () => {

            state.missionFilters
                .eventType =
                eventType.value;

            refreshMissionLog();
        }
    );
}


function setupRefreshControls() {
    $("historyRefresh")
        .addEventListener(
            "click",
            refreshHistory
        );

    $("missionLogRefresh")
        .addEventListener(
            "click",
            refreshMissionLog
        );

    $("missionLogExpand")
        .addEventListener(
            "click",
            () => {

                const panel =
                    document.querySelector(
                        ".mission-log"
                    );

                panel.classList.toggle(
                    "expanded"
                );
            }
        );
}


function initialize() {
    startClock();

    setupInteractionMode();
    setupDetailDrawer();
    setupMetricInteractions();
    setupOrbitInteraction();
    setupPipelineInteraction();
    setupMissionControls();
    setupRefreshControls();

    refreshMissionTypes();

    refreshAll();

    startPolling();
}


document.addEventListener(
    "DOMContentLoaded",
    initialize
);


/* ==========================================================================
   OrbitWatch Operating Mode Control
   ========================================================================== */

(function initializeOrbitWatchModeControl() {
    "use strict";

    const MODE_ID = "orbitwatch-runtime-mode";

    function createModeControl() {
        if (document.getElementById(MODE_ID)) {
            return;
        }

        const control = document.createElement("div");

        control.id = MODE_ID;
        control.innerHTML = `
            <div class="ow-mode-label">
                OPERATING MODE
            </div>

            <div class="ow-mode-controls">
                <button
                    type="button"
                    data-ow-mode="IDLE"
                    title="Return Mission Control to idle state"
                >
                    IDLE
                </button>

                <button
                    type="button"
                    data-ow-mode="REPLAY"
                    title="Replay is started with the development replay command"
                >
                    REPLAY
                </button>

                <button
                    type="button"
                    data-ow-mode="LIVE"
                    title="LIVE RF requires an active real SDR/input receiver"
                >
                    LIVE RF
                </button>
            </div>

            <div
                class="ow-mode-status"
                data-ow-mode-status
            >
                MODE: IDLE
            </div>
        `;

        const topbar =
            document.querySelector(
                "header"
            ) ||
            document.querySelector(
                ".topbar"
            ) ||
            document.querySelector(
                ".navbar"
            ) ||
            document.body.firstElementChild;

        if (topbar && topbar.parentNode) {
            topbar.parentNode.insertBefore(
                control,
                topbar.nextSibling
            );
        } else {
            document.body.prepend(control);
        }

        control
            .querySelectorAll(
                "[data-ow-mode]"
            )
            .forEach((button) => {
                button.addEventListener(
                    "click",
                    () => requestMode(
                        button.dataset.owMode
                    )
                );
            });
    }

    function updateModeControl(runtime) {
        const control =
            document.getElementById(
                MODE_ID
            );

        if (!control) {
            return;
        }

        const mode =
            String(
                runtime?.mode ||
                "IDLE"
            ).toUpperCase();

        const status =
            String(
                runtime?.status ||
                "idle"
            ).toUpperCase();

        const source =
            String(
                runtime?.data_source ||
                "NONE"
            ).toUpperCase();

        control.dataset.mode = mode;

        control
            .querySelectorAll(
                "[data-ow-mode]"
            )
            .forEach((button) => {
                button.classList.toggle(
                    "active",
                    button.dataset.owMode === mode
                );
            });

        const statusElement =
            control.querySelector(
                "[data-ow-mode-status]"
            );

        if (statusElement) {
            if (mode === "REPLAY") {
                statusElement.textContent =
                    "MODE: REPLAY / DEVELOPMENT";
            } else if (mode === "LIVE") {
                statusElement.textContent =
                    `MODE: LIVE RF • ${source} • ${status}`;
            } else {
                statusElement.textContent =
                    "MODE: IDLE • NO ACTIVE INPUT";
            }
        }
    }

    async function requestMode(mode) {
        if (mode === "REPLAY") {
            try {
                const response =
                    await fetch(
                        "/api/mode",
                        {
                            method: "POST",
                            headers: {
                                "Content-Type":
                                    "application/json",
                            },
                            body: JSON.stringify({
                                mode: "REPLAY",
                            }),
                        }
                    );

                const data =
                    await response.json();

                if (!response.ok) {
                    window.alert(
                        data.error ||
                        "Unable to start replay."
                    );

                    return;
                }

                updateModeControl(
                    data.runtime
                );

                // Refresh immediately so the dashboard can pick up
                // the replay-generated telemetry as soon as it exists.
                await refreshModeControl();

                if (typeof window.loadDashboardData === "function") {
                    try {
                        window.loadDashboardData();
                    } catch (error) {
                        console.debug(
                            "Dashboard refresh unavailable:",
                            error
                        );
                    }
                }

            } catch (error) {
                console.error(
                    "OrbitWatch replay start failed:",
                    error
                );

                window.alert(
                    "Unable to start REPLAY / DEVELOPMENT."
                );
            }

            return;
        }

        if (mode === "LIVE") {
            window.alert(
                "LIVE RF requires an active real SDR/input " +
                "receiver. OrbitWatch will not generate or " +
                "label synthetic telemetry as LIVE."
            );
            return;
        }

        try {
            const response =
                await fetch(
                    "/api/mode",
                    {
                        method: "POST",
                        headers: {
                            "Content-Type":
                                "application/json",
                        },
                        body: JSON.stringify({
                            mode: "IDLE",
                        }),
                    }
                );

            const data =
                await response.json();

            updateModeControl(
                data.runtime
            );

            if (!response.ok) {
                window.alert(
                    data.error ||
                    "Unable to change operating mode."
                );
            }
        } catch (error) {
            console.error(
                "OrbitWatch mode change failed:",
                error
            );
        }
    }

    async function refreshModeControl() {
        try {
            const response =
                await fetch(
                    "/api/mode",
                    {
                        cache: "no-store",
                    }
                );

            if (!response.ok) {
                return;
            }

            const data =
                await response.json();

            updateModeControl(
                data.runtime
            );
        } catch (error) {
            console.debug(
                "OrbitWatch runtime mode unavailable:",
                error
            );
        }
    }

    function start() {
        createModeControl();
        refreshModeControl();

        window.setInterval(
            refreshModeControl,
            2000
        );
    }

    if (
        document.readyState ===
        "loading"
    ) {
        document.addEventListener(
            "DOMContentLoaded",
            start,
            {
                once: true,
            }
        );
    } else {
        start();
    }
})();
