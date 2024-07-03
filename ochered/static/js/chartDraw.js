async function fetchData() {
  const response = await fetch(
    "http://91.185.12.100:8000/api/consultant-statistics/"
  );
  const data = await response.json();
  return data;
}

function humanizeTime(seconds) {
  const intervals = [
    ["год", "года", "лет", 31536000],
    ["месяц", "месяца", "месяцев", 2592000],
    ["неделя", "недели", "недель", 604800],
    ["день", "дня", "дней", 86400],
    ["час", "часа", "часов", 3600],
    ["минута", "минуты", "минут", 60],
    ["секунда", "секунды", "секунд", 1],
  ];
  let result = [];

  intervals.forEach(([one, few, many, count]) => {
    const value = Math.floor(seconds / count);
    if (value) {
      seconds -= value * count;
      let name;
      if (value % 10 === 1 && value % 100 !== 11) {
        name = one;
      } else if (
        2 <= value % 10 &&
        value % 10 <= 4 &&
        (value % 100 < 10 || value % 100 >= 20)
      ) {
        name = few;
      } else {
        name = many;
      }
      result.push(`${value} ${name}`);
    }
  });

  return result.join(", ");
}

function renderChart(data) {
  const ctx = document.getElementById("consultantChart").getContext("2d");
  const labels = data.map(
    (item) =>
      `${item.consultant__user__last_name} ${item.consultant__user__first_name}`
  );
  const avgServiceTimes = data.map((item) => item.avg_service_time);
  const ticketsServedToday = data.map((item) => item.tickets_served_today);
  const ticketsServedWeek = data.map((item) => item.tickets_served_week);
  const ticketsServedMonth = data.map((item) => item.tickets_served_month);

  const avgServiceTimesHumanized = avgServiceTimes.map((time) =>
    humanizeTime(time)
  );

  new Chart(ctx, {
    type: "bar",
    data: {
      labels: labels,
      datasets: [
        {
          label: "Среднее время обслуживания",
          type: "line",
          data: avgServiceTimes,
          backgroundColor: "rgb(46, 211, 152)",
          borderColor: "rgb(46, 211, 152)",
          borderWidth: 7,
          fill: false,
          yAxisID: "avgServiceTimeAxis",
        },
        {
          label: "Талоны обслужены сегодня",
          data: ticketsServedToday,
          backgroundColor: "rgb(255, 206, 86)",
          borderColor: "rgb(255, 206, 86)",
          borderWidth: 2,
          fill: false,
          yAxisID: "ticketsAxis",
        },
        {
          label: "Талоны обслужены на этой неделе",
          data: ticketsServedWeek,
          backgroundColor: "rgb(18, 48, 117)",
          borderColor: "rgb(9, 32, 86)",
          borderWidth: 2,
          fill: false,
          yAxisID: "ticketsAxis",
        },
        {
          label: "Талоны обслужены в этом месяце",
          data: ticketsServedMonth,
          backgroundColor: "rgb(249, 28, 61)",
          borderColor: "rgb(249, 28, 61)",
          borderWidth: 2,
          fill: false,
          yAxisID: "ticketsAxis",
        },
      ],
    },
    options: {
      responsive: true,
      scales: {
        x: {
          ticks: {
            color: "#000",
            font: {
              size: 14,
            },
          },
        },
        avgServiceTimeAxis: {
          position: "right",
          ticks: {
            color: "rgb(18, 48, 117)",
            font: {
              size: 16,
            },
            callback: function (value, index, values) {
              return humanizeTime(value);
            },
          },
        },
        ticketsAxis: {
          position: "left",
          ticks: {
            color: "#000",
            font: {
              size: 14,
            },
          },
        },
      },
      plugins: {
        tooltip: {
          callbacks: {
            label: function (context) {
              if (context.dataset.label === "Среднее время обслуживания") {
                return `Среднее время обслуживания: ${humanizeTime(
                  context.raw
                )}`;
              } else {
                return `${context.dataset.label}: ${context.raw}`;
              }
            },
          },
        },
        legend: {
          display: true,
          labels: {
            font: {
              size: 14,
            },
            padding: 20,
          },
        },
      },
    },
  });
}

async function updateChart() {
  const ctx = document.getElementById("consultantChart");
  if (Chart.getChart(ctx)) {
    Chart.getChart(ctx).destroy();
  }

  const data = await fetchData();
  renderChart(data);
}

setInterval(updateChart, 3600000); //1 час 
updateChart();
