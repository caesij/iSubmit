
let departmentComplianceChart = null;

function updateDepartmentComplianceChart(data) {
    const canvas = document.getElementById(
        "compliance-by-department-chart"
    );

    const emptyMessage = document.getElementById(
        "department-chart-empty"
    );

    if (!canvas || typeof Chart === "undefined") {
        return;
    }

    const departments = Array.isArray(data.compliance_by_department)
        ? data.compliance_by_department
        : [];

    // Check whether at least one program has applicable faculty.
    const hasComplianceData = departments.some(
        department => Number(department.faculty_count) > 0
    );

    // Show the empty message when no program has applicable faculty.
    if (!hasComplianceData) {
        if (departmentComplianceChart) {
            departmentComplianceChart.destroy();
            departmentComplianceChart = null;
        }

        canvas.hidden = true;

        if (emptyMessage) {
            emptyMessage.hidden = false;
        }

        return;
    }

    // Display the chart and hide the empty message.
    canvas.hidden = false;

    if (emptyMessage) {
        emptyMessage.hidden = true;
    }

    const labels = departments.map(
        department => department.program
    );

    const completedCounts = departments.map(
        department => Number(department.fully_compliant_count) || 0
    );

    // Display faculty counts and compliance percentage on hover.
    const tooltipCallback = function (context) {
        const department = departments[context.dataIndex];

        return [
            `Fully compliant: ${department.fully_compliant_count} of ${department.faculty_count} faculty`,
            `Compliance: ${department.compliance_percentage}%`
        ];
    };

    // Create the chart if it does not exist yet.
    if (!departmentComplianceChart) {
        departmentComplianceChart = new Chart(canvas, {
            type: "bar",

            data: {
                labels: labels,

                datasets: [{
                    label: "Fully Compliant Faculty",
                    data: completedCounts,
                    borderRadius: 5,
                    maxBarThickness: 60
                }]
            },

            options: {
                responsive: true,
                maintainAspectRatio: false,

                plugins: {
                    legend: {
                        display: false
                    },

                    tooltip: {
                        callbacks: {
                            label: tooltipCallback
                        }
                    }
                },

                scales: {
                    x: {
                        title: {
                            display: true,
                            text: "Program"
                        }
                    },

                    y: {
                        beginAtZero: true,

                        ticks: {
                            precision: 0
                        },

                        title: {
                            display: true,
                            text: "Number of Faculty Members"
                        }
                    }
                }
            }
        });

        return;
    }

    // Update the existing chart when new data arrives.
    departmentComplianceChart.data.labels = labels;

    departmentComplianceChart.data.datasets[0].data =
        completedCounts;

    departmentComplianceChart.options.plugins.tooltip.callbacks.label =
        tooltipCallback;

    departmentComplianceChart.update();
}
