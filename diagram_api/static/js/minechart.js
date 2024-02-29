function fetchData() {
  fetch("http://91.185.12.100:5000/api/diagram/")
    .then((response) => response.json())
    .then((data) => {
      const diagram1Data = data.diagram_1;
      delete diagram1Data["students"];
      const pieLabels = Object.keys(diagram1Data).map((key) => {
        switch (key) {
          case "students":
            return "Всего студентов";
          case "om":
            return "Общая медицина";
          case "stom":
            return "Стоматология";
          case "farm":
            return "Фармация";
          case "small_faculty":
            return "Маленькие факультеты";
          case "rez_mag_doc":
            return "Резидентура, Магистратура и Докторантура";
          default:
            return key;
        }
      });
      const pieValues = Object.values(diagram1Data);
      const total = pieValues.reduce((a, b) => a + b, 0);

      const pieDataElement = document.getElementById("pieData");
      pieDataElement.innerHTML = "<ul>";
      pieLabels.forEach((label, index) => {
        const percentage = ((pieValues[index] / total) * 100).toFixed(2);
        pieDataElement.innerHTML += `<li> ${label}: <span>${pieValues[index]} (${percentage}%)</span> </li> `;
      });
      pieDataElement.innerHTML += "</ul>";

      const pieChartCanvas = document
        .getElementById("pieChart")
        .getContext("2d");
      new Chart(pieChartCanvas, {
        type: "pie",
        data: {
          labels: pieLabels,
          datasets: [
            {
              data: pieValues,
              backgroundColor: [
                "rgba(54, 162, 235, 0.8)",
                "rgba(255, 206, 86, 0.8)",
                "rgba(75, 192, 192, 0.8)",
                "rgba(255, 99, 132, 1)",
                "rgba(255, 159, 64, 0.8)",
              ],
              borderWidth: 1,
            },
          ],
        },
        options: {
          responsive: true,
          aspectRatio: 3,

          legend: {
            display: true,
          },
        },
      });

      const diagram4Data = data.diagram_4;
      const barLabels = Object.keys(diagram4Data).map((key) => {
        switch (key) {
          case "om":
            return "Общая медицина";
          case "stom":
            return "Стоматология";
          case "oz":
            return "Общественное здравоохранение";
          case "farm":
            return "Фармация";
          case "sd":
            return "Сестринское дело";
          case "internatura":
            return "Интернатура";
          case "rezidentura":
            return "Резидентура";
          case "magistratura":
            return "Магистратура";
          case "doktorantura":
            return "Докторантура";
          default:
            return key;
        }
      });
      const barValues = Object.values(diagram4Data);

      const barDataElement = document.getElementById("barData");
      barDataElement.innerHTML = "<ul>";
      barLabels.forEach((label, index) => {
        barDataElement.innerHTML += `<li>${label}: <span>${barValues[index]}</span></li> `;
      });
      barDataElement.innerHTML += "</ul>";

      const barColors = [
        "rgba(171, 34, 116, 1)",
        "rgba(34, 59, 171, 1",
        "rgba(34, 171, 64, 1)",
        "rgba(220, 110, 18, 1)",
        "rgba(18, 167, 222, 1",
        "rgba(222, 21, 18, 1",
        "rgba(245, 181, 118, 1)",
        "rgba(255, 238, 0, 1)",
        "rgba(87, 87, 87, 1)",
      ];
      const barChartCanvas = document
        .getElementById("barChart")
        .getContext("2d");
      new Chart(barChartCanvas, {
        type: "bar",
        data: {
          labels: barLabels,
          datasets: [
            {
              label: "Количество студентов",
              data: barValues,
              backgroundColor: barColors,
              borderWidth: 1,
              display: true,
            },
          ],
        },
        options: {
          scales: {
            y: {
              beginAtZero: true,
            },
          },
          aspectRatio: 3,
        },
      });
    })
    .catch((error) => console.error("Error fetching data:", error));
}

fetchData();

setInterval(() => {
  location.reload();
}, 60 * 60 * 1000); // 60 минут * 60 секунд * 1000 миллисекунд = 1 час

setInterval(() => {
  fetchData();
  fetchChart();
}, 30 * 60 * 1000); // 30 минут * 60 секунд * 1000 миллисекунд = 30 минут

function generateColor() {
  function random(min, max) {
    return Math.floor(Math.random() * (max - min + 1)) + min;
  }

  let r = random(0, 255);
  let g = random(0, 255);
  let b = random(0, 255);

  if ((r > 200 && g > 200 && b > 200) || (r < 100 && g < 100 && b < 100)) {
    return generateColor();
  }

  for (let color of generatedColors) {
    let [oldR, oldG, oldB] = color.match(/\d+/g).map(Number);
    if (
      Math.abs(r - oldR) + Math.abs(g - oldG) + Math.abs(b - oldB) <
      255 * 0.05
    ) {
      return generateColor();
    }
  }

  let newColor = `rgba(${r}, ${g}, ${b}, ${random(35, 60) / 100})`;
  generatedColors.push(newColor);

  return newColor;
}

let generatedColors = [];

let markChart = null;

window.onload = function () {
  fetchChart();

  document
    .getElementById("chartForm")
    .addEventListener("submit", function (event) {
      event.preventDefault(); // Предотвращаем отправку формы по умолчанию

      let formData = new FormData(this);

      fetchChart(formData);
    });
};

function fetchChart(formData = null) {
  let url = "http://91.185.12.100:5000/api/get_marks/";
  if (formData) {
    url += "?" + new URLSearchParams(formData);
  }

  fetch(url)
    .then((response) => response.json())
    .then((data) => {
      // Уничтожаем предыдущий график, если он существует
      if (markChart) {
        markChart.destroy();
      }

      let messages = document.querySelectorAll(".alert-danger");
      messages.forEach((message) => message.remove());

      let labels = Object.keys(data.tutor_diagram);
      let marksCount = {};

      labels.forEach((label) => {
        if (data.tutor_diagram[label].marks === null) {
          let messageBlock = document.createElement("div");
          messageBlock.className = "alert alert-danger";
          messageBlock.role = "alert";
          messageBlock.innerText = `Нет оценок у преподавателя: ${data.tutor_diagram[label].fullName}`;

          let messageContainer = document.querySelector(".message-container");
          messageContainer.appendChild(messageBlock);
        } else {
          data.tutor_diagram[label].marks.forEach((mark) => {
            if (marksCount[mark]) {
              marksCount[mark]++;
            } else {
              marksCount[mark] = 1;
            }
          });
        }
      });

      // Находим оценку, которая встречается наиболее часто
      let mostFrequentMark = Object.keys(marksCount).reduce((a, b) =>
        marksCount[a] > marksCount[b] ? a : b
      );

      let marks = Object.keys(marksCount);
      let counts = Object.values(marksCount);

      let ctx = document.getElementById("markChart");
      markChart = new Chart(ctx, {
        type: "line",
        data: {
          labels: marks,
          datasets: [
            {
              label: "Частота оценок",
              data: counts,
              fill: true,
              borderColor: generateColor(),
              backgroundColor: generateColor(), // убрать если не нравится дизайн
              tension: 0.1,
            },
          ],
        },
        options: {
          interaction: {
            mode: "index",
            intersect: false,
          },
          plugins: {
            legend: {
              display: false,
            },
          },
          scales: {
            x: {
              title: {
                display: true,
                text: "Оценки",
              },
            },
            y: {
              title: {
                display: true,
                text: "Количество оценок",
              },
            },
          },
        },
      });

      console.log("Самая часто встречающаяся оценка:", mostFrequentMark);
    })
    .catch((error) => console.error("Error:", error));
}
