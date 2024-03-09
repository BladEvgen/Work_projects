async function fetchData(url) {
  const response = await fetch(url);
  return response.json();
}
async function countUniqueAges(filteredData) {
  const uniqueAges = new Set();

  filteredData.forEach((item) => {
    const birthDate = new Date(item.birthDate);
    const currentDate = new Date();
    const age = currentDate.getFullYear() - birthDate.getFullYear();
    uniqueAges.add(age);
  });

  console.log("Количество уникальных возрастов:", uniqueAges.size);
}
async function generateCharts() {
  try {
    const data = await fetchData(
      "https://platonus-mark.medkrmu.kz/dashboard/tutors"
    );

    console.log(data);

    const filteredData = data.data.filter((item) => item.has_access === "1");

    await generateCafedraChart(filteredData);
    await generateNameRuChart(filteredData);
    await generateRateChart(filteredData);
    await generateYearsChart(filteredData);
    await countUniqueAges(filteredData);
  } catch (error) {
    console.error("Ошибка:", error);
  }
}

async function generateCafedraChart(filteredData) {
  const cafedraCounts = {};
  filteredData.forEach((item) => {
    cafedraCounts[item.cafedraNameRu] =
      (cafedraCounts[item.cafedraNameRu] || 0) + 1;
  });

  const cafedraChartCanvas = document.getElementById("cafedraChart");
  const cafedraChartCtx = cafedraChartCanvas.getContext("2d");

  const sortedCafedraNames = Object.keys(cafedraCounts).sort().reverse();
  const sortedCafedraData = sortedCafedraNames.map(
    (name) => cafedraCounts[name]
  );

  const cafedraChart = new Chart(cafedraChartCtx, {
    type: "bar",
    data: {
      labels: sortedCafedraNames,
      datasets: [
        {
          label: "Кафедры",
          data: sortedCafedraData,
          backgroundColor: sortedCafedraNames.map(() => generateColor([], 0.5)),
        },
      ],
    },
    options: {
      responsive: true,
      scales: {
        y: {
          beginAtZero: true,
        },
      },
      plugins: {
        legend: {
          display: true,
        },
      },
    },
  });

  const cafedraChartLegend = document.getElementById("cafedraChartLegend");
  sortedCafedraNames.forEach((name, index) => {
    const color = cafedraChart.data.datasets[0].backgroundColor[index];
    cafedraChartLegend.innerHTML += `<div class="legend-item"><span class="legend-color" style="background-color: ${color}"></span>${name}: <strong>${cafedraCounts[name]}</strong></div>`;
  });
}

async function generateNameRuChart(filteredData) {
  const nameRuCounts = {};
  filteredData.forEach((item) => {
    const name = item.nameRu === "—" ? "Преподаватель" : item.nameRu;
    nameRuCounts[name] = (nameRuCounts[name] || 0) + 1;
  });

  const nameRuChartCtx = document
    .getElementById("nameRuChart")
    .getContext("2d");
  const nameRuChart = new Chart(nameRuChartCtx, {
    type: "doughnut",
    data: {
      labels: Object.keys(nameRuCounts),
      datasets: [
        {
          label: "Колличество",
          data: Object.values(nameRuCounts),
          backgroundColor: [
            "rgba(54, 162, 235, 0.8)",
            "rgba(255, 206, 86, 0.8)",
            "rgba(75, 192, 192, 0.8)",
            "rgba(255, 99, 132, 1)",
            "rgba(255, 159, 64, 0.8)",
          ],
        },
      ],
    },
    options: {
      responsive: true,
      plugins: {
        tooltip: {
          enabled: false,
        },
      },
      legend: {
        display: true,
      },
    },
  });

  const nameRuChartLegend = document.getElementById("nameRuChartLegend");
  Object.keys(nameRuCounts).forEach((name, index) => {
    const color = nameRuChart.data.datasets[0].backgroundColor[index];
    nameRuChartLegend.innerHTML += `<div class="legend-item"><span class="legend-color" style="background-color: ${color}"></span>${name}: <strong>${
      nameRuCounts[name]
    }(${((nameRuCounts[name] / filteredData.length) * 100).toFixed(
      2
    )}%)</strong></div>`;
  });
}

async function generateRateChart(filteredData) {
  const rateGroups = {};
  filteredData.forEach((item) => {
    const rate = parseFloat(item.rate);
    if (rate > 0) {
      if (!rateGroups[rate]) {
        rateGroups[rate] = 0;
      }
      rateGroups[rate]++;
    }
  });

  const sortedKeys = Object.keys(rateGroups)
    .map(parseFloat)
    .sort((a, b) => a - b);

  const sortedRateGroupsNumeric = {};
  sortedKeys.forEach((key) => {
    sortedRateGroupsNumeric[key] = rateGroups[key];
  });

  const rateChartCtx = document.getElementById("rateChart").getContext("2d");

  const rateChart = new Chart(rateChartCtx, {
    type: "pie",
    data: {
      labels: Object.keys(sortedRateGroupsNumeric).map((rate) =>
        rate.toString()
      ),
      datasets: [
        {
          label: "Колличество",
          data: Object.values(sortedRateGroupsNumeric),
          backgroundColor: [
            "rgba(255, 99, 71, 0.8)", // Томатный
            "rgba(255, 165, 0, 0.8)", // Оранжевый
            "rgba(255, 20, 147, 0.8)", // Глубокий розовый
            "rgba(70, 130, 180, 1)", // Стальной голубой
            "rgba(218, 112, 214, 0.8)", // Фуксия
            "rgba(173, 255, 47, 0.8)", // Зеленый желтоватый
          ],
        },
      ],
    },
    options: {
      responsive: true,
      plugins: {
        tooltip: {
          enabled: false,
        },
      },
      legend: {
        display: true,
      },
    },
  });

  const rateChartLegend = document.getElementById("rateChartLegend");
  Object.keys(sortedRateGroupsNumeric).forEach((rate, index) => {
    const color = rateChart.data.datasets[0].backgroundColor[index];
    rateChartLegend.innerHTML += `<div class="legend-item"><span class="legend-color" style="background-color: ${color}"></span>Ставка ${rate}:<strong> ${
      sortedRateGroupsNumeric[rate]
    } чел. (${(
      (sortedRateGroupsNumeric[rate] / filteredData.length) *
      100
    ).toFixed(2)}%)</div></strong>`;
  });
}

async function generateYearsChart(filteredData) {
  const yearsCounts = {};

  filteredData.forEach((item) => {
    const birthDate = new Date(item.birthDate);
    const currentDate = new Date();
    const age = currentDate.getFullYear() - birthDate.getFullYear();

    if (!yearsCounts[age]) {
      yearsCounts[age] = 0;
    }
    yearsCounts[age]++;
  });

  const sortedYears = Object.keys(yearsCounts).sort((a, b) => a - b);
  const yearsData = sortedYears.map((year) => yearsCounts[year]);

  const yearsChartCanvas = document.getElementById("yearsChart");
  const yearsChartCtx = yearsChartCanvas.getContext("2d");

  const yearsChart = new Chart(yearsChartCtx, {
    type: "line",
    data: {
      labels: sortedYears,
      datasets: [
        {
          label: "Количество преподавателей",
          data: yearsData,
          borderColor: "rgba(255, 99, 132, 1)",
          backgroundColor: "rgba(255, 99, 132, 0.2)",
        },
      ],
    },
    options: {
      responsive: true,
      scales: {
        x: {
          title: {
            display: true,
            text: "Возраст преподавателей",
          },
        },
        y: {
          title: {
            display: true,
            text: "Количество преподавателей",
          },
          beginAtZero: true,
        },
      },
      plugins: {
        legend: {
          display: false,
        },
      },
    },
  });

  const yearsChartLegend = document.getElementById("yearsChartLegend");
  yearsChartLegend.innerHTML = "";

  sortedYears.forEach((year) => {
    const legendItem = document.createElement("div");
    legendItem.classList.add("legend-item");

    const span = document.createElement("span");
    span.textContent = `${year} лет: `;
    legendItem.appendChild(span);

    const strong = document.createElement("strong");
    strong.textContent = yearsCounts[year];
    legendItem.appendChild(strong);

    yearsChartLegend.appendChild(legendItem);
  });
}

function generateColor(existingColors, uniqueness) {
  function random(min, max) {
    return Math.floor(Math.random() * (max - min + 1)) + min;
  }

  let h, s, l;
  let maxAttempts = 100;
  let attempt = 0;

  do {
    h = random(0, 360); // Генерация случайного оттенка
    s = random(50, 100); // Насыщенность от 50% до 100%
    l = random(20, 80); // Светлота от 20% до 80%
    attempt++;
  } while (
    attempt < maxAttempts &&
    (existingColors.some(
      (color) => colorSimilarity(color, `hsl(${h}, ${s}%, ${l}%)`) < uniqueness
    ) ||
      (s <= 10 && l >= 90)) // Игнорировать белые цвета
  );

  return `hsl(${h}, ${s}%, ${l}%)`;
}

function scheduleGenerateCharts() {
  generateCharts();
  setInterval(generateCharts, 6 * 60 * 60 * 1000); // 6 часов
}

scheduleGenerateCharts();

//test
